from odoo import api, fields, models


class CustomerVisit(models.Model):
    _name = 'customer.visit'
    _description = 'Visita a cliente'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Referencia', required=True, readonly=True, copy=False, default='Nueva')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True, index=True, tracking=True)
    user_id = fields.Many2one(
        'res.users', string='Responsable', default=lambda self: self.env.user, tracking=True)
    date = fields.Datetime(
        string='Fecha', required=True, default=fields.Datetime.now, tracking=True)
    visit_type = fields.Selection([
        ('onsite', 'Presencial'),
        ('virtual', 'Virtual'),
        ('phone', 'Telefónica'),
    ], string='Tipo', required=True, default='onsite', tracking=True)
    state = fields.Selection([
        ('planned', 'Planificada'),
        ('done', 'Realizada'),
        ('cancelled', 'Cancelada'),
    ], string='Estado', required=True, default='planned', copy=False, tracking=True,
        group_expand=True)
    notes = fields.Html(string='Minuta')
    next_visit_date = fields.Date(string='Próxima visita', tracking=True)
    company_id = fields.Many2one(
        'res.company', string='Compañía', default=lambda self: self.env.company)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', 'Nueva') == 'Nueva':
                vals['name'] = self.env['ir.sequence'].next_by_code('customer.visit') or 'Nueva'
        return super().create(vals_list)

    def action_done(self):
        self.write({'state': 'done'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_to_planned(self):
        self.write({'state': 'planned'})
