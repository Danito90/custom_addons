from odoo import api, fields, models
from odoo.tools import SQL


class ResPartner(models.Model):
    _inherit = 'res.partner'

    has_payable_debt = fields.Boolean(
        string='Con deuda a pagar', compute='_compute_payable_flags', search='_search_has_payable_debt')
    has_overdue_payable = fields.Boolean(
        string='Con vencidos a pagar', compute='_compute_payable_flags', search='_search_has_overdue_payable')

    @api.model
    def _get_payable_partner_ids(self, overdue=False):
        """ Proveedores (commercial partner) a los que se les debe o con vencidos.

        Misma regla que el estado de cuenta de proveedores: apuntes a pagar publicados, en las
        empresas del proveedor que el usuario tiene habilitadas (o en todas las del usuario si el
        proveedor no tiene "Empresas en las que participa"). La deuda se evalúa por moneda de la
        empresa y, con signo contable, es un pendiente negativo.
        """
        self.env['account.move.line'].flush_model(
            ['account_id', 'parent_state', 'company_id', 'partner_id', 'amount_residual', 'date_maturity'])
        self.env['res.partner'].flush_model(['commercial_partner_id'])
        base = SQL("""
            FROM account_move_line aml
            JOIN account_account account ON account.id = aml.account_id
            JOIN res_partner partner ON partner.id = aml.partner_id
            JOIN res_company company ON company.id = aml.company_id
           WHERE account.account_type = 'liability_payable'
             AND aml.parent_state = 'posted'
             AND aml.company_id = ANY(%s)
             AND (
                 NOT EXISTS (SELECT 1 FROM res_partner_statement_company_rel rel
                              WHERE rel.partner_id = partner.commercial_partner_id)
                 OR EXISTS (SELECT 1 FROM res_partner_statement_company_rel rel
                             WHERE rel.partner_id = partner.commercial_partner_id
                               AND rel.company_id = aml.company_id)
             )
        """, self.env.user.company_ids.ids)
        if overdue:
            query = SQL("""
                SELECT DISTINCT partner.commercial_partner_id %s
                   AND aml.amount_residual < 0
                   AND aml.date_maturity < %s
            """, base, fields.Date.context_today(self))
        else:
            query = SQL("""
                SELECT partner.commercial_partner_id %s
                 GROUP BY partner.commercial_partner_id, company.currency_id
                HAVING SUM(aml.amount_residual) < 0
            """, base)
        self.env.cr.execute(query)
        return list({row[0] for row in self.env.cr.fetchall()})

    @api.depends_context('uid')
    def _compute_payable_flags(self):
        debt = set(self._get_payable_partner_ids())
        overdue = set(self._get_payable_partner_ids(overdue=True))
        for partner in self:
            commercial = partner.commercial_partner_id.id
            partner.has_payable_debt = commercial in debt
            partner.has_overdue_payable = commercial in overdue

    def _search_has_payable_debt(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._get_payable_partner_ids())]

    def _search_has_overdue_payable(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._get_payable_partner_ids(overdue=True))]
