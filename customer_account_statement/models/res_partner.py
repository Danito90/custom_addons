from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    company_ids = fields.Many2many(
        'res.company', 'res_partner_statement_company_rel', 'partner_id', 'company_id',
        string='Empresas en las que participa',
        help='Empresas en las que se puede consultar el estado de cuenta del cliente. '
             'Vacío: todas las empresas habilitadas del usuario.')

    def action_open_account_statement(self):
        self.ensure_one()
        partner = self.commercial_partner_id
        self.env['customer.account.statement']._check_partner_access(partner)
        action = self.env['ir.actions.act_window']._for_xml_id(
            'customer_account_statement.action_customer_account_statement')
        action['context'] = {'default_partner_id': partner.id}
        return action
