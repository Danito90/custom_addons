from odoo import Command, api, fields, models
from odoo.exceptions import AccessError
from odoo.tools import SQL

# Grupos que siempre ven todo en la app, aunque el ajuste esté activado.
FULL_ACCESS_GROUPS = (
    'account.group_account_invoice',
    'sales_team.group_sale_salesman_all_leads',
    'sales_team.group_sale_manager',
)
# Grupos que pueden asignar vendedores.
ASSIGN_GROUPS = ('account.group_account_invoice', 'sales_team.group_sale_manager')

# Menú de la app -> (acción de ventana, campo que indica el vendedor del cliente).
APP_ACTIONS = {
    'customers': ('customer_management.action_customer_management_customers_window', 'user_id'),
    'invoices': ('customer_management.action_customer_management_invoices_window',
                 'commercial_partner_id.user_id'),
    'payments': ('customer_management.action_customer_management_payments_window',
                 'partner_id.commercial_partner_id.user_id'),
    'overdue': ('customer_management.action_customer_management_overdue_window',
                'commercial_partner_id.user_id'),
    'visits': ('customer_visit.customer_visit_action', 'partner_id.commercial_partner_id.user_id'),
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    has_receivable_debt = fields.Boolean(
        string='Con deuda', compute='_compute_receivable_flags', search='_search_has_receivable_debt')
    has_overdue_debt = fields.Boolean(
        string='Con vencidos', compute='_compute_receivable_flags', search='_search_has_overdue_debt')
    can_assign_salesman = fields.Boolean(
        string='Puede asignar vendedor', compute='_compute_can_assign_salesman')

    # -------------------------------------------------------------------------
    # Deuda
    # -------------------------------------------------------------------------

    @api.model
    def _get_receivable_partner_ids(self, overdue=False):
        """ Clientes (commercial partner) con deuda o con vencidos.

        Misma regla que el estado de cuenta: apuntes a cobrar publicados, en las empresas del
        cliente que el usuario tiene habilitadas (o en todas las del usuario si el cliente no
        tiene "Empresas en las que participa"). La deuda se evalúa por moneda de la empresa.
        """
        base = SQL("""
            FROM account_move_line aml
            JOIN account_account account ON account.id = aml.account_id
            JOIN res_partner partner ON partner.id = aml.partner_id
            JOIN res_company company ON company.id = aml.company_id
           WHERE account.account_type = 'asset_receivable'
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
                   AND aml.amount_residual > 0
                   AND aml.date_maturity < %s
            """, base, fields.Date.context_today(self))
        else:
            query = SQL("""
                SELECT partner.commercial_partner_id %s
                 GROUP BY partner.commercial_partner_id, company.currency_id
                HAVING SUM(aml.amount_residual) > 0
            """, base)
        self.env.cr.execute(query)
        return list({row[0] for row in self.env.cr.fetchall()})

    @api.depends_context('uid')
    def _compute_receivable_flags(self):
        debt = set(self._get_receivable_partner_ids())
        overdue = set(self._get_receivable_partner_ids(overdue=True))
        for partner in self:
            commercial = partner.commercial_partner_id.id
            partner.has_receivable_debt = commercial in debt
            partner.has_overdue_debt = commercial in overdue

    def _search_has_receivable_debt(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._get_receivable_partner_ids())]

    def _search_has_overdue_debt(self, operator, value):
        if operator != 'in':
            return NotImplemented
        return [('id', 'in', self._get_receivable_partner_ids(overdue=True))]

    # -------------------------------------------------------------------------
    # Vendedores
    # -------------------------------------------------------------------------

    @api.model
    def _customer_management_can_assign(self):
        return any(self.env.user.has_group(group) for group in ASSIGN_GROUPS)

    @api.depends_context('uid')
    def _compute_can_assign_salesman(self):
        can_assign = self._customer_management_can_assign()
        for partner in self:
            partner.can_assign_salesman = can_assign

    @api.model
    def _customer_management_is_restricted(self):
        """ True si el usuario debe ver solo sus clientes dentro de la app. """
        if not self.env['ir.config_parameter'].sudo().get_bool(
                'customer_management.salesman_own_customers_only'):
            return False
        user = self.env.user
        return (user.has_group('sales_team.group_sale_salesman')
                and not any(user.has_group(group) for group in FULL_ACCESS_GROUPS))

    # -------------------------------------------------------------------------
    # Alta de clientes
    # -------------------------------------------------------------------------

    @api.model
    def default_get(self, fields):
        """ Alta desde la app Clientes: empresa activa y, si quien crea es vendedor, Vendedor.
        No aplica a contactos hijos que se cargan dentro de la ficha. """
        values = super().default_get(fields)
        context = self.env.context
        if context.get('partner_vat_check_scope') == 'customer' and not context.get('default_parent_id'):
            if 'company_ids' in fields and not values.get('company_ids'):
                values['company_ids'] = [Command.set(self.env.company.ids)]
            if ('user_id' in fields and not values.get('user_id')
                    and self.env.user.has_group('sales_team.group_sale_salesman')):
                values['user_id'] = self.env.uid
        return values

    def action_customer_management_new_customer(self):
        """ Botón "Nuevo cliente" del listado: abre la ficha completa con el contexto de la app.
        Sin @api.model: el botón de cabecera lo llama con los ids seleccionados (o ninguno). """
        if not self.has_access('create'):
            raise AccessError(self.env._(
                'No tenés permiso para crear clientes. Pedile a un administrador el permiso '
                '"Creación de contactos".'))
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Nuevo cliente'),
            'res_model': 'res.partner',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'current',
            'context': {
                'default_is_company': True,
                'default_customer_rank': 1,
                'res_partner_search_mode': 'customer',
                'partner_vat_check_scope': 'customer',
            },
        }

    # -------------------------------------------------------------------------
    # Menús de la app
    # -------------------------------------------------------------------------

    @api.model
    def _get_customer_management_base_domain(self, key):
        today = fields.Date.context_today(self)
        return {
            'customers': ['|', ('is_company', '=', True), ('parent_id', '=', False)],
            'invoices': [('move_type', 'in', ('out_invoice', 'out_refund'))],
            'payments': [('partner_type', '=', 'customer'), ('payment_type', '=', 'inbound')],
            'overdue': [
                ('move_type', '=', 'out_invoice'),
                ('state', '=', 'posted'),
                ('payment_state', 'in', ('not_paid', 'partial')),
                ('invoice_date_due', '<', today),
            ],
            'visits': [],
        }[key]

    @api.model
    def action_customer_management_open(self, key):
        """ Abre un menú de la app aplicando el ajuste "Vendedores ven solo sus clientes". """
        xmlid, salesman_field = APP_ACTIONS[key]
        action = self.env['ir.actions.act_window']._for_xml_id(xmlid)
        domain = self._get_customer_management_base_domain(key)
        if self._customer_management_is_restricted():
            domain = domain + [(salesman_field, '=', self.env.uid)]
        action['domain'] = domain
        return action
