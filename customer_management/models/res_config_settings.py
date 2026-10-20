from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    salesman_own_customers_only = fields.Boolean(
        string='Vendedores ven solo sus clientes',
        config_parameter='customer_management.salesman_own_customers_only',
        help='Solo dentro de la app Clientes. En Contactos, Facturación y el resto de Odoo '
             'los vendedores siguen viendo todos los clientes.')
