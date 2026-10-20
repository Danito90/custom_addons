from odoo import fields, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    visit_ids = fields.One2many('customer.visit', 'partner_id', string='Visitas')
    visit_count = fields.Integer(string='Cantidad de visitas', compute='_compute_visit_count')

    def _compute_visit_count(self):
        counts = dict(self.env['customer.visit']._read_group(
            [('partner_id', 'in', self.ids)], ['partner_id'], ['__count']))
        for partner in self:
            partner.visit_count = counts.get(partner, 0)

    def action_view_visits(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('customer_visit.customer_visit_action')
        action['domain'] = [('partner_id', '=', self.id)]
        action['context'] = {'default_partner_id': self.id}
        return action
