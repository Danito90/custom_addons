from odoo import models


class CustomerAccountStatementReconcile(models.TransientModel):
    _inherit = 'customer.account.statement.reconcile'

    def action_reconcile(self):
        self.ensure_one()
        if (self.partner_type == 'supplier'
                and self.env['customer.account.statement']._is_purchase_statement_user()):
            # sudo: Compras no tiene permiso estándar sobre los asientos de pago. Antes se verifica
            # el permiso (casilla de Ajustes); super() valida además cliente, empresa, cuenta e importes.
            self._check_reconcile_access()
            return super(CustomerAccountStatementReconcile, self.sudo()).action_reconcile()
        return super().action_reconcile()
