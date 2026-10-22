from datetime import datetime, time

import pytz

from odoo import api, fields, models
from odoo.exceptions import UserError


class StockControlKardexWizard(models.TransientModel):
    _name = 'stock.control.kardex.wizard'
    _description = 'Ficha por producto (kardex)'

    product_id = fields.Many2one(
        'product.product', 'Producto', required=True, domain="[('is_storable', '=', True)]")
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Depósito', domain="[('company_id', '=', company_id)]",
        help='Vacío: todos los depósitos de la empresa.')
    company_id = fields.Many2one('res.company', required=True, default=lambda self: self.env.company)
    date_from = fields.Date('Desde', required=True, default=lambda self: fields.Date.context_today(self).replace(day=1))
    date_to = fields.Date('Hasta', required=True, default=fields.Date.context_today)

    @api.constrains('date_from', 'date_to')
    def _check_dates(self):
        for wizard in self:
            if wizard.date_from > wizard.date_to:
                raise UserError(self.env._('La fecha "Desde" tiene que ser anterior o igual a "Hasta".'))

    def _get_period_bounds(self):
        """Inicio y fin del período en UTC, según la zona horaria del usuario."""
        self.ensure_one()
        tz = pytz.timezone(self.env.user.tz or 'UTC')
        start = tz.localize(datetime.combine(self.date_from, time.min)).astimezone(pytz.UTC).replace(tzinfo=None)
        end = tz.localize(datetime.combine(self.date_to, time.max)).astimezone(pytz.UTC).replace(tzinfo=None)
        return start, end

    def _get_base_domain(self):
        self.ensure_one()
        domain = [
            ('state', '=', 'done'),
            ('product_id', '=', self.product_id.id),
            ('company_id', '=', self.company_id.id),
            ('stock_control_signed_qty', '!=', 0),
        ]
        if self.warehouse_id:
            domain.append(('stock_control_warehouse_id', '=', self.warehouse_id.id))
        return domain

    def _get_kardex_data(self):
        """Saldo inicial, movimientos del período con saldo acumulado y saldo final."""
        self.ensure_one()
        Move = self.env['stock.move']
        start, end = self._get_period_bounds()
        base = self._get_base_domain()
        [[initial]] = Move._read_group(base + [('date', '<', start)], aggregates=['stock_control_signed_qty:sum'])
        initial = initial or 0.0
        moves = Move.search(base + [('date', '>=', start), ('date', '<=', end)], order='date, id')
        rows = []
        balance = initial
        for move in moves:
            qty = move.stock_control_signed_qty
            balance += qty
            rows.append({
                'move': move,
                'qty_in': qty if qty > 0 else 0.0,
                'qty_out': -qty if qty < 0 else 0.0,
                'balance': balance,
            })
        return {
            'initial': initial,
            'rows': rows,
            'total_in': sum(row['qty_in'] for row in rows),
            'total_out': sum(row['qty_out'] for row in rows),
            'final': balance,
        }

    def action_print(self):
        return self.env.ref('stock_control.action_report_kardex').report_action(self)

    def action_view_moves(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock_control.action_stock_control_audit_moves')
        start, end = self._get_period_bounds()
        action['domain'] = self._get_base_domain() + [('date', '>=', start), ('date', '<=', end)]
        action['context'] = {}
        return action
