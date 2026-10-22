from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError

from .stock_control_manual_move import (
    LOCK_FREE_FIELD_PREFIXES,
    stock_control_inventory_location,
    stock_control_location_qty,
    stock_control_next_name,
)

THEORETICAL_MODES = [
    ('on_save', 'Al guardar'),
    ('on_start', 'Al iniciar el conteo'),
]

INVENTORY_STATES = [
    ('draft', 'Borrador'),
    ('in_progress', 'En conteo'),
    ('done', 'Guardado'),
    ('reopened', 'Reabierto'),
    ('cancel', 'Cancelado'),
]

EVENT_TYPES = [
    ('start', 'Inicio del conteo'),
    ('save', 'Guardado'),
    ('reopen', 'Reapertura'),
    ('resave', 'Guardado después de reabrir'),
    ('cancel', 'Cancelación'),
]

MANAGER_GROUP = 'stock_control.group_stock_control_manager'


class StockControlInventory(models.Model):
    _name = 'stock.control.inventory'
    _description = 'Control de inventario'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='/')
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Depósito', required=True, check_company=True, tracking=True,
        default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1))
    category_ids = fields.Many2many('product.category', string='Categorías', required=True)
    include_child_categories = fields.Boolean('Incluir subcategorías', default=True)
    date = fields.Date('Fecha', required=True, default=fields.Date.context_today, tracking=True)
    theoretical_mode = fields.Selection(
        THEORETICAL_MODES, 'Comparar contra', readonly=True, copy=False,
        help='Se copia de Ajustes al iniciar el conteo.')
    state = fields.Selection(
        INVENTORY_STATES, 'Estado', default='draft', required=True, readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one(related='warehouse_id.company_id', store=True, string='Empresa')
    line_ids = fields.One2many('stock.control.inventory.line', 'inventory_id', 'Líneas', copy=False)
    event_ids = fields.One2many('stock.control.inventory.event', 'inventory_id', 'Historial', copy=False)
    move_ids = fields.One2many('stock.move', 'stock_control_inventory_id', 'Movimientos de ajuste', copy=False)
    is_locked = fields.Boolean(compute='_compute_is_locked')
    line_count = fields.Integer('Cantidad de líneas', compute='_compute_line_stats')
    counted_line_count = fields.Integer('Contadas', compute='_compute_line_stats')
    diff_line_count = fields.Integer('Con diferencia', compute='_compute_line_stats')

    @api.depends('state')
    def _compute_is_locked(self):
        for record in self:
            record.is_locked = record.state in ('done', 'cancel')

    @api.depends('line_ids.line_state')
    def _compute_line_stats(self):
        for record in self:
            record.line_count = len(record.line_ids)
            record.counted_line_count = len(record.line_ids.filtered('is_counted'))
            record.diff_line_count = len(record.line_ids.filtered(lambda line: line.line_state == 'diff'))

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == '/':
                record.name = stock_control_next_name(self.env, 'stock_control.inventory', record.company_id)
        return records

    def write(self, vals):
        if not self.env.context.get('stock_control_allow_write'):
            locked_fields = [f for f in vals if not f.startswith(LOCK_FREE_FIELD_PREFIXES)]
            if locked_fields:
                for record in self:
                    if record.is_locked:
                        raise UserError(record._locked_message())
                    if record.state != 'draft' and {'warehouse_id', 'category_ids', 'include_child_categories'} & set(vals):
                        raise UserError(self.env._('El depósito y las categorías solo se cambian en Borrador.'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_draft(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(self.env._('Solo se puede borrar un control de inventario en Borrador. '
                                       'Si ya se inició, cancelalo.'))

    def _locked_message(self):
        self.ensure_one()
        if self.state == 'cancel':
            return self.env._('El control %(name)s está cancelado.', name=self.name)
        return self.env._('El control %(name)s está guardado. Solo un administrador puede reabrirlo.', name=self.name)

    def _write_state(self, vals):
        return self.with_context(stock_control_allow_write=True).write(vals)

    def _log_event(self, event_type, reason=False, adjusted_line_count=0):
        # sudo: el historial es de solo lectura para los usuarios; lo escribe únicamente el código.
        self.env['stock.control.inventory.event'].sudo().create([{
            'inventory_id': record.id,
            'event_type': event_type,
            'user_id': self.env.user.id,
            'reason': reason,
            'adjusted_line_count': adjusted_line_count,
        } for record in self])

    def _get_products_to_count(self):
        self.ensure_one()
        operator = 'child_of' if self.include_child_categories else 'in'
        return self.env['product.product'].search([
            ('is_storable', '=', True),
            ('categ_id', operator, self.category_ids.ids),
            ('company_id', 'in', [False, self.company_id.id]),
        ])

    def action_start(self):
        mode = self.env['ir.config_parameter'].sudo().get_str('stock_control.theoretical_mode') or 'on_save'
        if mode not in dict(THEORETICAL_MODES):
            mode = 'on_save'
        for record in self:
            if record.state != 'draft':
                raise UserError(self.env._('Solo se puede iniciar el conteo de un control en Borrador.'))
            products = record._get_products_to_count()
            if not products:
                raise UserError(self.env._('Las categorías elegidas no tienen productos con seguimiento de inventario.'))
            quants = self.env['stock.quant'].sudo().search([
                ('product_id', 'in', products.ids),
                ('location_id.usage', '=', 'internal'),
                ('location_id.warehouse_id', '=', record.warehouse_id.id),
                ('lot_id', '=', False),
            ])
            qty_by_key = defaultdict(float)
            for quant in quants:
                qty_by_key[quant.product_id, quant.location_id] += quant.quantity
            line_vals = []
            products_with_stock = set()
            for (product, location), qty in qty_by_key.items():
                if product.uom_id.is_zero(qty):
                    continue
                products_with_stock.add(product)
                line_vals.append(record._prepare_line_vals(product, location, qty, mode))
            for product in products - products.browse([p.id for p in products_with_stock]):
                line_vals.append(record._prepare_line_vals(product, record.warehouse_id.lot_stock_id, 0.0, mode))
            record._write_state({
                'state': 'in_progress',
                'theoretical_mode': mode,
                'line_ids': [fields.Command.create(vals) for vals in line_vals],
            })
            record._log_event('start')
        return True

    def _prepare_line_vals(self, product, location, qty, mode):
        return {
            'product_id': product.id,
            'location_id': location.id,
            'theoretical_qty': qty if mode == 'on_start' else 0.0,
        }

    def _get_line_adjustment(self, line):
        """Cantidad a ajustar en la línea y teórico a guardar (None si no cambia)."""
        if line.is_applied:
            return line.counted_qty - line.applied_counted_qty, None
        if self.theoretical_mode == 'on_save':
            current = stock_control_location_qty(line.product_id, line.location_id)
            return line.counted_qty - current, current
        return line.counted_qty - line.theoretical_qty, None

    def action_save(self):
        for record in self:
            if record.state not in ('in_progress', 'reopened'):
                raise UserError(self.env._('Solo se puede guardar un control En conteo o Reabierto.'))
            if record.line_ids.filtered(lambda line: line.is_applied and not line.is_counted):
                raise UserError(self.env._('Una línea que ya se ajustó no puede quedar como No contada. '
                                           'Cargá su cantidad.'))
            event_type = 'resave' if record.state == 'reopened' else 'save'
            move_vals = []
            line_updates = []
            for line in record.line_ids.filtered('is_counted'):
                delta, theoretical = record._get_line_adjustment(line)
                update = {'applied_counted_qty': line.counted_qty, 'is_applied': True}
                if theoretical is not None:
                    update['theoretical_qty'] = theoretical
                line_updates.append((line, update))
                if not line.uom_id.is_zero(delta):
                    move_vals.append(record._prepare_adjustment_move_vals(line, delta))
            if move_vals:
                moves = self.env['stock.move'].with_context(inventory_mode=False).create(move_vals)
                moves._action_done()
            for line, update in line_updates:
                line.with_context(stock_control_allow_write=True).write(update)
            record._write_state({'state': 'done'})
            record._log_event(event_type, adjusted_line_count=len(move_vals))
        return True

    def _prepare_adjustment_move_vals(self, line, delta):
        self.ensure_one()
        inventory_location = stock_control_inventory_location(line.product_id, self.company_id)
        qty = abs(delta)
        if delta > 0:
            location, location_dest = inventory_location, line.location_id
        else:
            location, location_dest = line.location_id, inventory_location
        return {
            'product_id': line.product_id.id,
            'uom_id': line.product_id.uom_id.id,
            'product_uom_qty': qty,
            'company_id': self.company_id.id,
            'state': 'confirmed',
            'location_id': location.id,
            'location_dest_id': location_dest.id,
            'is_inventory': True,
            'inventory_name': self.name,
            'picked': True,
            'stock_control_inventory_id': self.id,
            'stock_control_inventory_line_id': line.id,
            'move_line_ids': [fields.Command.create({
                'product_id': line.product_id.id,
                'uom_id': line.product_id.uom_id.id,
                'quantity': qty,
                'location_id': location.id,
                'location_dest_id': location_dest.id,
                'company_id': self.company_id.id,
            })],
        }

    def _check_manager(self):
        if not self.env.user.has_group(MANAGER_GROUP):
            raise AccessError(self.env._('Solo un administrador de Control de inventario puede reabrir un control.'))

    def action_reopen(self):
        self.ensure_one()
        self._check_manager()
        if self.state != 'done':
            raise UserError(self.env._('Solo se puede reabrir un control Guardado.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Reabrir control'),
            'res_model': 'stock.control.reopen.wizard',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {'default_inventory_id': self.id},
        }

    def _reopen(self, reason):
        self._check_manager()
        if not (reason or '').strip():
            raise UserError(self.env._('Escribí el motivo de la reapertura.'))
        for record in self:
            if record.state != 'done':
                raise UserError(self.env._('Solo se puede reabrir un control Guardado.'))
            record._write_state({'state': 'reopened'})
            record._log_event('reopen', reason=reason)

    def action_cancel(self):
        for record in self:
            if record.state not in ('draft', 'in_progress'):
                raise UserError(self.env._('Solo se puede cancelar un control en Borrador o En conteo.'))
            record._write_state({'state': 'cancel'})
            record._log_event('cancel')
        return True

    def action_print_sheet(self):
        return self.env.ref('stock_control.action_report_count_sheet').report_action(self)

    def action_print_differences(self):
        return self.env.ref('stock_control.action_report_differences').report_action(self)

    def action_view_moves(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock_control.action_stock_control_audit_moves')
        action['domain'] = [('stock_control_inventory_id', '=', self.id)]
        action['context'] = {}
        return action

    def _get_sheet_groups(self):
        """Líneas agrupadas por ubicación y categoría, para la planilla y el informe."""
        self.ensure_one()
        groups = defaultdict(lambda: self.env['stock.control.inventory.line'])
        for line in self.line_ids.sorted(lambda l: (l.location_id.complete_name or '', l.categ_id.complete_name or '',
                                                    l.default_code or '', l.product_id.display_name or '')):
            groups[line.location_id, line.categ_id] |= line
        return [(location, categ, lines) for (location, categ), lines in groups.items()]

    def _sheet_show_theoretical(self):
        return self.env['ir.config_parameter'].sudo().get_bool('stock.show_expected_quantity_count')


class StockControlInventoryLine(models.Model):
    _name = 'stock.control.inventory.line'
    _description = 'Línea de control de inventario'
    _order = 'location_id, categ_id, default_code, product_id'

    inventory_id = fields.Many2one('stock.control.inventory', 'Control', required=True, ondelete='cascade', index=True)
    inventory_state = fields.Selection(related='inventory_id.state', string='Estado del control', store=True)
    warehouse_id = fields.Many2one(related='inventory_id.warehouse_id', string='Depósito', store=True)
    date = fields.Date(related='inventory_id.date', string='Fecha', store=True)
    company_id = fields.Many2one(related='inventory_id.company_id', string='Empresa', store=True)
    product_id = fields.Many2one(
        'product.product', 'Producto', required=True,
        domain="[('is_storable', '=', True), ('company_id', 'in', [False, company_id])]")
    default_code = fields.Char(related='product_id.default_code', string='Código', store=True)
    categ_id = fields.Many2one(related='product_id.categ_id', string='Categoría', store=True)
    location_id = fields.Many2one(
        'stock.location', 'Ubicación', required=True,
        domain="[('usage', '=', 'internal'), ('warehouse_id', '=', warehouse_id)]")
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')
    theoretical_qty = fields.Float('Teórico', digits='Product Unit', readonly=True)
    counted_qty = fields.Float('Contado', digits='Product Unit')
    is_counted = fields.Boolean('Contada', help='Sin tildar: la línea es No contada y no se ajusta. '
                                                'Para indicar que no hay stock, cargá 0 y tildala.')
    applied_counted_qty = fields.Float('Conteo aplicado', digits='Product Unit', readonly=True)
    is_applied = fields.Boolean('Aplicada', readonly=True)
    difference_qty = fields.Float(
        'Diferencia', digits='Product Unit', compute='_compute_difference_qty', store=True)
    line_state = fields.Selection(
        [('not_counted', 'No contada'), ('ok', 'Sin diferencia'), ('diff', 'Con diferencia')],
        string='Estado', compute='_compute_difference_qty', store=True)
    move_ids = fields.One2many('stock.move', 'stock_control_inventory_line_id', 'Movimientos')

    _unique_product_location = models.Constraint(
        'unique(inventory_id, product_id, location_id)',
        'El producto ya está en esa ubicación dentro del control.')
    _counted_qty_positive = models.Constraint(
        'CHECK(counted_qty >= 0)',
        'La cantidad contada no puede ser negativa.')

    @api.depends('counted_qty', 'theoretical_qty', 'is_counted', 'product_id.uom_id')
    def _compute_difference_qty(self):
        for line in self:
            if not line.is_counted:
                line.difference_qty = 0.0
                line.line_state = 'not_counted'
                continue
            line.difference_qty = line.counted_qty - line.theoretical_qty
            line.line_state = 'ok' if line.product_id.uom_id.is_zero(line.difference_qty) else 'diff'

    @api.onchange('counted_qty')
    def _onchange_counted_qty(self):
        if self.counted_qty:
            self.is_counted = True

    def _check_inventory_editable(self):
        if self.env.context.get('stock_control_allow_write'):
            return
        for line in self:
            if line.inventory_id.state not in ('in_progress', 'reopened'):
                if line.inventory_id.is_locked:
                    raise UserError(line.inventory_id._locked_message())
                raise UserError(self.env._('Las líneas se cargan después de "Iniciar conteo".'))

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('counted_qty'):
                vals.setdefault('is_counted', True)
        lines = super().create(vals_list)
        lines._check_inventory_editable()
        if not self.env.context.get('stock_control_allow_write'):
            # Línea agregada a mano: en modo "Al iniciar el conteo" toma la existencia de ese momento.
            for line in lines.filtered(lambda l: l.inventory_id.theoretical_mode == 'on_start'):
                line.with_context(stock_control_allow_write=True).theoretical_qty = \
                    stock_control_location_qty(line.product_id, line.location_id)
        return lines

    def write(self, vals):
        self._check_inventory_editable()
        if not self.env.context.get('stock_control_allow_write'):
            if {'product_id', 'location_id'} & set(vals) and any(line.is_applied for line in self):
                raise UserError(self.env._('No se puede cambiar el producto ni la ubicación de una línea ya ajustada.'))
            protected = {'theoretical_qty', 'applied_counted_qty', 'is_applied'} & set(vals)
            if protected:
                raise UserError(self.env._('Esos valores los calcula el sistema.'))
            if vals.get('counted_qty'):
                vals = dict(vals, is_counted=vals.get('is_counted', True))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_locked(self):
        self._check_inventory_editable()
        if any(line.is_applied for line in self):
            raise UserError(self.env._('No se puede borrar una línea que ya se ajustó.'))


class StockControlInventoryEvent(models.Model):
    _name = 'stock.control.inventory.event'
    _description = 'Evento de control de inventario'
    _order = 'date desc, id desc'

    inventory_id = fields.Many2one('stock.control.inventory', 'Control', required=True, ondelete='cascade', index=True)
    event_type = fields.Selection(EVENT_TYPES, 'Evento', required=True)
    user_id = fields.Many2one('res.users', 'Usuario', required=True, default=lambda self: self.env.user)
    date = fields.Datetime('Fecha', required=True, default=fields.Datetime.now)
    reason = fields.Text('Motivo')
    adjusted_line_count = fields.Integer('Líneas ajustadas')
