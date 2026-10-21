from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    purchase_can_reconcile = fields.Boolean(
        string='Compras puede imputar',
        config_parameter='supplier_management.purchase_can_reconcile')
    purchase_can_unreconcile = fields.Boolean(
        string='Compras puede desimputar',
        config_parameter='supplier_management.purchase_can_unreconcile')
    purchase_can_send = fields.Boolean(
        string='Compras puede enviar el estado de cuenta por email',
        config_parameter='supplier_management.purchase_can_send')
