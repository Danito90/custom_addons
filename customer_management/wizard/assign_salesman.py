from odoo import api, fields, models
from odoo.exceptions import AccessError


class CustomerManagementAssignSalesman(models.TransientModel):
    _name = 'customer.management.assign.salesman'
    _description = 'Asignar vendedor a clientes'

    @api.model
    def _default_partner_ids(self):
        if self.env.context.get('active_model') != 'res.partner':
            return self.env['res.partner']
        return self.env['res.partner'].browse(self.env.context.get('active_ids', []))

    partner_ids = fields.Many2many(
        'res.partner', string='Clientes', required=True, default=_default_partner_ids)
    user_id = fields.Many2one(
        'res.users', string='Vendedor', domain="[('share', '=', False)]",
        help='Vacío: se quita el vendedor de los clientes elegidos.')

    def action_assign(self):
        self.ensure_one()
        if not self.env['res.partner']._customer_management_can_assign():
            raise AccessError(self.env._(
                'Solo los usuarios de Facturación y los gerentes de ventas pueden asignar vendedores.'))
        # Grupo ya validado: se escribe con sudo porque Facturación y Gerente de ventas no
        # siempre tienen el permiso estándar para editar contactos.
        self.partner_ids.sudo().write({'user_id': self.user_id.id})
        return {'type': 'ir.actions.act_window_close'}
