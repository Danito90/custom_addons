from odoo import fields, models

from .res_partner import VAT_CHECK_POLICIES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    # Cada app (Clientes / Proveedores) muestra el suyo en su sección de Ajustes.
    customer_vat_duplicate_policy = fields.Selection(
        VAT_CHECK_POLICIES, string='CUIT repetido en Clientes',
        config_parameter='partner_vat_check.customer_policy',
        help='Qué pasa al guardar desde la app Clientes un cliente con el CUIT de otro cliente activo.')
    supplier_vat_duplicate_policy = fields.Selection(
        VAT_CHECK_POLICIES, string='CUIT repetido en Proveedores',
        config_parameter='partner_vat_check.supplier_policy',
        help='Qué pasa al guardar desde la app Proveedores un proveedor con el CUIT de otro proveedor activo.')
