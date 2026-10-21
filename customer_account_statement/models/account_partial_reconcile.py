from odoo import api, fields, models
from odoo.exceptions import AccessError


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    statement_counterpart_line_id = fields.Many2one(
        'account.move.line', string='Comprobante contraparte',
        compute='_compute_statement_counterpart')
    statement_counterpart_move_id = fields.Many2one(
        'account.move', string='Contraparte', compute='_compute_statement_counterpart')
    statement_can_unreconcile = fields.Boolean(
        string='Puede desimputar', compute='_compute_statement_can_unreconcile')

    @api.depends_context('statement_move_line_id')
    @api.depends('debit_move_id', 'credit_move_id')
    def _compute_statement_counterpart(self):
        line_id = self.env.context.get('statement_move_line_id')
        for partial in self:
            if partial.debit_move_id.id == line_id:
                counterpart = partial.credit_move_id
            else:
                counterpart = partial.debit_move_id
            partial.statement_counterpart_line_id = counterpart
            partial.statement_counterpart_move_id = counterpart.move_id

    def _get_statement_partner_type(self):
        """ 'supplier' si la imputación es entre apuntes a pagar; si no, 'customer'. """
        self.ensure_one()
        if self.debit_move_id.account_id.account_type == 'liability_payable':
            return 'supplier'
        return 'customer'

    @api.depends_context('uid')
    @api.depends('debit_move_id')
    def _compute_statement_can_unreconcile(self):
        Statement = self.env['customer.account.statement']
        for partial in self:
            partial.statement_can_unreconcile = Statement._can_unreconcile(
                partial._get_statement_partner_type())

    def _check_statement_unreconcile_access(self):
        Statement = self.env['customer.account.statement']
        for partial in self:
            if not Statement._can_unreconcile(partial._get_statement_partner_type()):
                raise AccessError(self.env._('No tenés permiso para desimputar.'))

    def action_statement_unreconcile(self):
        self._check_statement_unreconcile_access()
        self.unlink()
        statement = self.env['customer.account.statement'].browse(
            self.env.context.get('active_statement_id')).exists()
        if statement:
            statement._generate_lines()
        return True
