from odoo import fields, models


class StockControlReopenWizard(models.TransientModel):
    _name = 'stock.control.reopen.wizard'
    _description = 'Reabrir control de inventario'

    inventory_id = fields.Many2one('stock.control.inventory', 'Control', required=True)
    reason = fields.Text('Motivo de la reapertura', required=True)

    def action_confirm(self):
        self.ensure_one()
        self.inventory_id._reopen(self.reason)
        return {'type': 'ir.actions.act_window_close'}
