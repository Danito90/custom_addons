from odoo import api, models


class CustomerAccountStatement(models.TransientModel):
    _inherit = 'customer.account.statement'

    @api.model
    def _is_purchase_statement_user(self):
        """ Usuario de Compras sin Facturación. """
        user = self.env.user
        return (user.has_group('purchase.group_purchase_user')
                and not user.has_group('account.group_account_invoice'))

    @api.model
    def _purchase_can(self, partner_type, action):
        """ True si Compras tiene habilitada la acción (casilla de Ajustes) en la cuenta de proveedor. """
        return (partner_type == 'supplier'
                and self.env.user.has_group('purchase.group_purchase_user')
                and self.env['ir.config_parameter'].sudo().get_bool(
                    f'supplier_management.purchase_can_{action}'))

    @api.model
    def _check_partner_access(self, partner, partner_type='customer'):
        # Compras consulta e imprime la cuenta de todos los proveedores, sin comprador asignado.
        if partner_type == 'supplier' and self.env.user.has_group('purchase.group_purchase_user'):
            return
        return super()._check_partner_access(partner, partner_type)

    @api.model
    def _can_reconcile(self, partner_type):
        return super()._can_reconcile(partner_type) or self._purchase_can(partner_type, 'reconcile')

    @api.model
    def _can_unreconcile(self, partner_type):
        return super()._can_unreconcile(partner_type) or self._purchase_can(partner_type, 'unreconcile')

    @api.model
    def _can_send(self, partner_type):
        return super()._can_send(partner_type) or self._purchase_can(partner_type, 'send')
