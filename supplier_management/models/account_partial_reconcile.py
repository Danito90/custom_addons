from odoo import models


class AccountPartialReconcile(models.Model):
    _inherit = 'account.partial.reconcile'

    def action_statement_unreconcile(self):
        if self.env['customer.account.statement']._is_purchase_statement_user():
            # sudo: Compras no puede borrar imputaciones. Antes se verifica el permiso (casilla de
            # Ajustes), que además exige que todas las imputaciones sean de cuentas a pagar.
            self._check_statement_unreconcile_access()
            return super(AccountPartialReconcile, self.sudo()).action_statement_unreconcile()
        return super().action_statement_unreconcile()
