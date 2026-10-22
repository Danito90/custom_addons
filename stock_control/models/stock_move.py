from odoo import api, fields, models

STOCK_CONTROL_ORIGINS = [
    ('purchase', 'Compra'),
    ('sale', 'Venta'),
    ('manual', 'Movimiento manual'),
    ('inventory', 'Control de inventario'),
    ('scrap', 'Desecho'),
    ('other', 'Otro'),
]


class StockMove(models.Model):
    _inherit = 'stock.move'

    stock_control_manual_move_id = fields.Many2one(
        'stock.control.manual.move', 'Movimiento manual', index='btree_not_null', readonly=True)
    stock_control_inventory_id = fields.Many2one(
        'stock.control.inventory', 'Control de inventario', index='btree_not_null', readonly=True)
    stock_control_inventory_line_id = fields.Many2one(
        'stock.control.inventory.line', 'Línea de control', index='btree_not_null', readonly=True)
    stock_control_reason_id = fields.Many2one('stock.control.reason', 'Motivo propio', readonly=True)
    stock_control_reason_text = fields.Char(
        'Motivo', compute='_compute_stock_control_reason_text', store=True)
    stock_control_origin = fields.Selection(
        STOCK_CONTROL_ORIGINS, 'Origen', compute='_compute_stock_control_origin', store=True)
    stock_control_done_user_id = fields.Many2one('res.users', 'Validado por', readonly=True)
    stock_control_signed_qty = fields.Float(
        'Cantidad (±)', digits='Product Unit', compute='_compute_stock_control_signed_qty', store=True,
        help='Positiva si entra a una ubicación interna, negativa si sale, cero entre ubicaciones internas.')
    stock_control_warehouse_id = fields.Many2one(
        'stock.warehouse', 'Depósito', compute='_compute_stock_control_warehouse_id', store=True)
    stock_control_categ_id = fields.Many2one(
        related='product_id.categ_id', string='Categoría', store=True)

    @api.depends('stock_control_manual_move_id.name')
    def _compute_reference(self):
        super()._compute_reference()
        for move in self.filtered('stock_control_manual_move_id'):
            move.reference = move.stock_control_manual_move_id.name

    @api.depends('stock_control_inventory_id', 'stock_control_manual_move_id', 'is_scrap',
                 'purchase_line_id', 'sale_line_id')
    def _compute_stock_control_origin(self):
        for move in self:
            if move.stock_control_inventory_id:
                move.stock_control_origin = 'inventory'
            elif move.stock_control_manual_move_id:
                move.stock_control_origin = 'manual'
            elif move.is_scrap:
                move.stock_control_origin = 'scrap'
            elif move.purchase_line_id:
                move.stock_control_origin = 'purchase'
            elif move.sale_line_id:
                move.stock_control_origin = 'sale'
            else:
                move.stock_control_origin = 'other'

    @api.depends('stock_control_reason_id.name', 'scrap_reason_tag_ids.name', 'is_inventory',
                 'inventory_name', 'stock_control_inventory_id')
    def _compute_stock_control_reason_text(self):
        for move in self:
            if move.stock_control_reason_id:
                move.stock_control_reason_text = move.stock_control_reason_id.name
            elif move.scrap_reason_tag_ids:
                move.stock_control_reason_text = ', '.join(move.scrap_reason_tag_ids.mapped('name'))
            elif move.is_inventory and not move.stock_control_inventory_id:
                move.stock_control_reason_text = move.inventory_name or False
            else:
                move.stock_control_reason_text = False

    @api.depends('quantity', 'uom_id', 'product_id.uom_id', 'location_id.usage', 'location_dest_id.usage')
    def _compute_stock_control_signed_qty(self):
        for move in self:
            qty = move.uom_id._compute_quantity(move.quantity, move.product_id.uom_id) if move.uom_id else move.quantity
            src_internal = move.location_id.usage == 'internal'
            dest_internal = move.location_dest_id.usage == 'internal'
            if dest_internal and not src_internal:
                move.stock_control_signed_qty = qty
            elif src_internal and not dest_internal:
                move.stock_control_signed_qty = -qty
            else:
                move.stock_control_signed_qty = 0.0

    @api.depends('location_id.warehouse_id', 'location_dest_id.warehouse_id', 'location_dest_id.usage')
    def _compute_stock_control_warehouse_id(self):
        for move in self:
            if move.location_dest_id.usage == 'internal':
                move.stock_control_warehouse_id = move.location_dest_id.warehouse_id
            else:
                move.stock_control_warehouse_id = move.location_id.warehouse_id

    def _action_done(self, cancel_backorder=False):
        moves = super()._action_done(cancel_backorder=cancel_backorder)
        moves.filtered(lambda m: m.state == 'done' and not m.stock_control_done_user_id).write({
            'stock_control_done_user_id': self.env.user.id,
        })
        return moves
