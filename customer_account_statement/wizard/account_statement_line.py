from odoo import fields, models
from odoo.exceptions import AccessError


class CustomerAccountStatementLine(models.TransientModel):
    _name = 'customer.account.statement.line'
    _description = 'Línea de estado de cuenta de cliente'
    _order = 'currency_id, sequence'

    statement_id = fields.Many2one(
        'customer.account.statement', string='Estado de cuenta', required=True, ondelete='cascade')
    sequence = fields.Integer(string='Secuencia')
    line_type = fields.Selection([
        ('initial', 'Saldo inicial'),
        ('move', 'Movimiento'),
    ], string='Tipo de línea', required=True, default='move')
    company_id = fields.Many2one('res.company', string='Empresa')
    currency_id = fields.Many2one('res.currency', string='Moneda')
    move_line_id = fields.Many2one('account.move.line', string='Apunte')
    move_id = fields.Many2one('account.move', string='Asiento')
    payment_id = fields.Many2one('account.payment', string='Pago')
    document_type = fields.Char(string='Tipo')
    date = fields.Date(string='Fecha')
    date_maturity = fields.Date(string='Vencimiento')
    name = fields.Char(string='Comprobante')
    debit = fields.Monetary(string='Debe')
    credit = fields.Monetary(string='Haber')
    balance = fields.Monetary(
        string='Importe', help='Debe menos Haber. La suma de la columna es el saldo final.')
    cumulative_balance = fields.Monetary(string='Saldo acumulado')
    original_currency_id = fields.Many2one('res.currency', string='Moneda original')
    amount_currency = fields.Monetary(
        string='Importe en moneda original', currency_field='original_currency_id')
    amount_residual = fields.Monetary(string='Pendiente')
    days_overdue = fields.Integer(string='Días de atraso')
    is_reconciled = fields.Boolean(string='Imputado totalmente')
    is_reconcile_source = fields.Boolean(
        string='Imputable', help='Recibo o NC de cliente, o pago o NC de proveedor, que se puede '
                                 'imputar a facturas.')

    def action_open_document(self):
        self.ensure_one()
        if self.payment_id:
            model, res_id = 'account.payment', self.payment_id.id
        else:
            model, res_id = 'account.move', self.move_id.id
        return {
            'type': 'ir.actions.act_window',
            'res_model': model,
            'res_id': res_id,
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
        }

    def action_view_reconciliations(self):
        self.ensure_one()
        move_line = self.move_line_id
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Imputaciones de %s', self.name),
            'res_model': 'account.partial.reconcile',
            'view_mode': 'list',
            'views': [(self.env.ref(
                'customer_account_statement.account_partial_reconcile_view_list_statement').id, 'list')],
            'domain': ['|', ('debit_move_id', '=', move_line.id), ('credit_move_id', '=', move_line.id)],
            'context': {
                'statement_move_line_id': move_line.id,
                'active_statement_id': self.statement_id.id,
                'create': False,
            },
            'target': 'current',
        }

    def action_open_reconcile_wizard(self):
        self.ensure_one()
        statement = self.statement_id
        if not statement._can_reconcile(statement.partner_type):
            raise AccessError(self.env._('No tenés permiso para imputar.'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Imputar %s', self.name),
            'res_model': 'customer.account.statement.reconcile',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_credit_line_id': self.move_line_id.id,
                'default_statement_id': self.statement_id.id,
            },
        }
