from collections import defaultdict

from odoo import api, fields, models
from odoo.exceptions import UserError

MANUAL_MOVE_TYPES = [
    ('in', 'Entrada'),
    ('out', 'Salida'),
]

# Campos que se pueden escribir en un registro bloqueado (los escribe el chatter).
LOCK_FREE_FIELD_PREFIXES = ('message_', 'activity_')


def stock_control_next_name(env, code, company):
    """Devuelve el próximo número de la secuencia `code` para `company`.

    Las secuencias base del módulo no tienen empresa. La primera vez que una
    empresa numera se crea una copia propia, así cada empresa tiene su
    numeración (MM/2026/0001 en cada una).
    """
    Sequence = env['ir.sequence'].sudo()  # sudo: los usuarios del módulo no tienen permisos sobre ir.sequence
    sequence = Sequence.search([('code', '=', code), ('company_id', '=', company.id)], limit=1)
    if not sequence:
        base = Sequence.search([('code', '=', code), ('company_id', '=', False)], limit=1)
        if not base:
            raise UserError(env._('Falta la secuencia %(code)s. Actualizá el módulo Control de inventario.', code=code))
        sequence = base.copy({'company_id': company.id, 'number_next': 1, 'date_range_ids': False})
    return sequence.next_by_id()


def stock_control_inventory_location(product, company):
    """Ubicación de ajuste de inventario del producto en la empresa, como stock.quant._apply_inventory."""
    location = product.with_company(company).property_stock_inventory
    if not location:
        location_id = product.env['ir.default'].with_company(company)._get_model_defaults(
            'product.template').get('property_stock_inventory')
        location = product.env['stock.location'].browse(location_id)
    if not location:
        raise UserError(product.env._('La empresa %(company)s no tiene ubicación de ajuste de inventario.',
                                      company=company.name))
    return location


def stock_control_location_qty(product, location):
    """Existencia del producto en la ubicación exacta (sin ubicaciones hijas)."""
    quants = product.env['stock.quant'].sudo()._gather(product, location, strict=True)
    return sum(quants.mapped('quantity'))


class StockControlManualMove(models.Model):
    _name = 'stock.control.manual.move'
    _description = 'Movimiento manual de stock'
    _inherit = ['mail.thread']
    _order = 'date desc, id desc'
    _check_company_auto = True

    name = fields.Char('Número', readonly=True, copy=False, default='/')
    move_type = fields.Selection(MANUAL_MOVE_TYPES, string='Tipo', required=True, default='in', tracking=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Depósito', required=True, check_company=True,
        default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.company.id)], limit=1))
    location_id = fields.Many2one(
        'stock.location', 'Ubicación', required=True, check_company=True,
        domain="[('usage', '=', 'internal'), ('warehouse_id', '=', warehouse_id)]")
    date = fields.Datetime('Fecha', required=True, default=fields.Datetime.now, tracking=True)
    reason_id = fields.Many2one(
        'stock.control.reason', 'Motivo', required=True, tracking=True, check_company=True,
        domain="[('move_type', 'in', [move_type, 'both'])]")
    note = fields.Text('Observación')
    state = fields.Selection(
        [('draft', 'Borrador'), ('done', 'Confirmado'), ('cancel', 'Cancelado')],
        string='Estado', default='draft', required=True, readonly=True, copy=False, tracking=True)
    company_id = fields.Many2one(related='warehouse_id.company_id', store=True, string='Empresa')
    line_ids = fields.One2many('stock.control.manual.move.line', 'manual_move_id', 'Líneas', copy=True)
    move_ids = fields.One2many('stock.move', 'stock_control_manual_move_id', 'Movimientos de stock')
    reversed_move_id = fields.Many2one(
        'stock.control.manual.move', 'Revierte a', readonly=True, copy=False, index='btree_not_null')
    reversal_ids = fields.One2many('stock.control.manual.move', 'reversed_move_id', 'Reversiones')
    can_reverse = fields.Boolean(compute='_compute_can_reverse')

    @api.depends('state', 'reversal_ids.state', 'reversed_move_id')
    def _compute_can_reverse(self):
        for record in self:
            record.can_reverse = (
                record.state == 'done'
                and not record.reversed_move_id
                and not record.reversal_ids.filtered(lambda r: r.state == 'done'))

    @api.onchange('warehouse_id')
    def _onchange_warehouse_id(self):
        if self.location_id.warehouse_id != self.warehouse_id:
            self.location_id = self.warehouse_id.lot_stock_id

    @api.onchange('move_type')
    def _onchange_move_type(self):
        if self.reason_id and self.reason_id.move_type not in (self.move_type, 'both'):
            self.reason_id = False

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.name == '/':
                record.name = stock_control_next_name(self.env, 'stock_control.manual_move', record.company_id)
        return records

    def write(self, vals):
        if not self.env.context.get('stock_control_allow_write'):
            locked_fields = [f for f in vals if not f.startswith(LOCK_FREE_FIELD_PREFIXES)]
            if locked_fields and any(record.state == 'done' for record in self):
                raise UserError(self.env._('Un movimiento manual confirmado no se puede modificar. '
                                           'Para corregirlo, usá "Revertir".'))
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_confirmed(self):
        if any(record.state == 'done' for record in self):
            raise UserError(self.env._('Un movimiento manual confirmado no se puede borrar. '
                                       'Para corregirlo, usá "Revertir".'))

    def _check_can_confirm(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(self.env._('Solo se puede confirmar un movimiento manual en Borrador.'))
            if not record.line_ids:
                raise UserError(self.env._('Cargá al menos un producto para confirmar %(name)s.', name=record.name))
            # Una reversión conserva el motivo del original aunque sea de otro tipo.
            if not record.reversed_move_id and record.reason_id.move_type not in (record.move_type, 'both'):
                raise UserError(self.env._('El motivo %(reason)s no aplica a este tipo de movimiento.',
                                           reason=record.reason_id.name))
            if record.location_id.usage != 'internal' or record.location_id.warehouse_id != record.warehouse_id:
                raise UserError(self.env._('La ubicación tiene que ser una ubicación interna del depósito elegido.'))
            if any(line.quantity <= 0 for line in record.line_ids):
                raise UserError(self.env._('Las cantidades tienen que ser mayores a cero.'))
            if record.move_type == 'out':
                record._check_available_quantity()

    def _check_available_quantity(self):
        self.ensure_one()
        requested = defaultdict(float)
        for line in self.line_ids:
            requested[line.product_id] += line.quantity
        for product, qty in requested.items():
            available = stock_control_location_qty(product, self.location_id)
            if product.uom_id.compare(qty, available) > 0:
                raise UserError(self.env._(
                    'No hay stock suficiente de %(product)s en %(location)s: hay %(available)s y querés sacar %(qty)s.',
                    product=product.display_name, location=self.location_id.complete_name,
                    available=available, qty=qty))

    def _prepare_stock_move_vals(self, line):
        self.ensure_one()
        inventory_location = stock_control_inventory_location(line.product_id, self.company_id)
        if self.move_type == 'in':
            location, location_dest = inventory_location, self.location_id
        else:
            location, location_dest = self.location_id, inventory_location
        return {
            'product_id': line.product_id.id,
            'uom_id': line.product_id.uom_id.id,
            'product_uom_qty': line.quantity,
            'company_id': self.company_id.id,
            'state': 'confirmed',
            'location_id': location.id,
            'location_dest_id': location_dest.id,
            'picked': True,
            'stock_control_manual_move_id': self.id,
            'stock_control_reason_id': self.reason_id.id,
            'move_line_ids': [fields.Command.create({
                'product_id': line.product_id.id,
                'uom_id': line.product_id.uom_id.id,
                'quantity': line.quantity,
                'location_id': location.id,
                'location_dest_id': location_dest.id,
                'company_id': self.company_id.id,
            })],
        }

    def action_confirm(self):
        self._check_can_confirm()
        for record in self:
            move_vals = [record._prepare_stock_move_vals(line) for line in record.line_ids]
            moves = self.env['stock.move'].create(move_vals)
            moves._action_done()
            record.with_context(stock_control_allow_write=True).write({'state': 'done'})
        return True

    def action_cancel(self):
        if any(record.state != 'draft' for record in self):
            raise UserError(self.env._('Solo se puede cancelar un movimiento manual en Borrador.'))
        self.write({'state': 'cancel'})
        return True

    def action_draft(self):
        if any(record.state != 'cancel' for record in self):
            raise UserError(self.env._('Solo se puede volver a Borrador un movimiento cancelado.'))
        self.write({'state': 'draft'})
        return True

    def action_reverse(self):
        self.ensure_one()
        if not self.can_reverse:
            raise UserError(self.env._('Este movimiento no se puede revertir: no está confirmado, '
                                       'ya fue revertido o es una reversión.'))
        reversal = self.create({
            'move_type': 'out' if self.move_type == 'in' else 'in',
            'warehouse_id': self.warehouse_id.id,
            'location_id': self.location_id.id,
            'reason_id': self.reason_id.id,
            'note': self.env._('Reversión de %(name)s', name=self.name),
            'reversed_move_id': self.id,
            'line_ids': [fields.Command.create({'product_id': line.product_id.id, 'quantity': line.quantity})
                         for line in self.line_ids],
        })
        reversal.action_confirm()
        self.message_post(body=self.env._('Revertido por %(name)s.', name=reversal.name))
        return {
            'type': 'ir.actions.act_window',
            'res_model': self._name,
            'res_id': reversal.id,
            'view_mode': 'form',
            'views': [(False, 'form')],
        }


class StockControlManualMoveLine(models.Model):
    _name = 'stock.control.manual.move.line'
    _description = 'Línea de movimiento manual de stock'

    manual_move_id = fields.Many2one(
        'stock.control.manual.move', required=True, ondelete='cascade', index=True)
    product_id = fields.Many2one(
        'product.product', 'Producto', required=True,
        domain="[('is_storable', '=', True), ('company_id', 'in', [False, parent.company_id])]")
    quantity = fields.Float('Cantidad', required=True, digits='Product Unit', default=1.0)
    uom_id = fields.Many2one(related='product_id.uom_id', string='Unidad')

    def _check_parent_editable(self):
        if not self.env.context.get('stock_control_allow_write') and \
                any(line.manual_move_id.state == 'done' for line in self):
            raise UserError(self.env._('Un movimiento manual confirmado no se puede modificar. '
                                       'Para corregirlo, usá "Revertir".'))

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        lines._check_parent_editable()
        return lines

    def write(self, vals):
        self._check_parent_editable()
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_not_draft(self):
        self._check_parent_editable()
