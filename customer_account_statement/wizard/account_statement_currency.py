from odoo import fields, models


class CustomerAccountStatementCurrency(models.TransientModel):
    _name = 'customer.account.statement.currency'
    _description = 'Saldo de estado de cuenta por moneda'
    _order = 'id'

    statement_id = fields.Many2one(
        'customer.account.statement', string='Estado de cuenta', required=True, ondelete='cascade')
    currency_id = fields.Many2one('res.currency', string='Moneda', required=True)
    initial_balance = fields.Monetary(string='Saldo inicial')
    debit = fields.Monetary(string='Debe')
    credit = fields.Monetary(string='Haber')
    final_balance = fields.Monetary(string='Saldo final')
    amount_residual = fields.Monetary(string='Total adeudado')
