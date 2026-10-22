from odoo import fields, models

REASON_MOVE_TYPES = [
    ('in', 'Entrada'),
    ('out', 'Salida'),
    ('both', 'Ambos'),
]


class StockControlReason(models.Model):
    _name = 'stock.control.reason'
    _description = 'Motivo de movimiento de stock'
    _order = 'sequence, name'

    name = fields.Char('Motivo', required=True, translate=True)
    sequence = fields.Integer(default=10)
    move_type = fields.Selection(REASON_MOVE_TYPES, string='Aplica en', required=True, default='both')
    active = fields.Boolean(default=True)
    company_id = fields.Many2one('res.company', 'Empresa', help='Vacío: el motivo vale para todas las empresas.')
