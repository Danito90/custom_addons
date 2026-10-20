from odoo import api, fields, models
from odoo.exceptions import AccessError


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    statement_counterpart_line_id = fields.Many2one(
        'account.move.line', string='Comprobante contraparte',
        compute='_compute_statement_counterpart')
    statement_counterpart_move_id = fields.Many2one(
        'account.move', string='Contraparte', compute='_compute_statement_counterpart')

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

    def action_statement_unreconcile(self):
        if not self.env.user.has_group('account.group_account_invoice'):
            raise AccessError(self.env._('Solo los usuarios de Facturación pueden desimputar.'))
        self.unlink()
        statement = self.env['customer.account.statement'].browse(
            self.env.context.get('active_statement_id')).exists()
        if statement:
            statement._generate_lines()
        return True
