from odoo import models


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    def action_stock_control_audit_moves(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('stock_control.action_stock_control_audit_moves')
        action['domain'] = [('state', '=', 'done'), ('product_id', 'in', self.product_variant_ids.ids)]
        action['context'] = {}
        action['display_name'] = self.env._('Movimientos de %(product)s', product=self.display_name)
        return action
