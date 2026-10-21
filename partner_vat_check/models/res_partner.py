import re

from odoo import api, models
from odoo.exceptions import ValidationError
from odoo.tools import SQL

# Clave de contexto que ponen las apps Clientes y Proveedores en sus acciones.
VAT_CHECK_CONTEXT_KEY = 'partner_vat_check_scope'

VAT_CHECK_POLICIES = [
    ('block', 'Bloquear'),
    ('warn', 'Avisar'),
    ('none', 'No controlar'),
]

VAT_CHECK_SCOPES = {
    # scope: (parámetro del ajuste, campo de rango, etiqueta)
    'customer': ('partner_vat_check.customer_policy', 'customer_rank', 'cliente'),
    'supplier': ('partner_vat_check.supplier_policy', 'supplier_rank', 'proveedor'),
}


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _normalize_vat_for_check(self, vat):
        """ CUIT sin guiones, puntos ni espacios, en mayúsculas. """
        return re.sub(r'[^0-9A-Za-z]', '', vat or '').upper()

    @api.model
    def _get_vat_check_scope(self):
        """ 'customer' / 'supplier' si se guarda desde la app correspondiente; si no, False. """
        scope = self.env.context.get(VAT_CHECK_CONTEXT_KEY)
        return scope if scope in VAT_CHECK_SCOPES else False

    @api.model
    def _get_vat_check_policy(self, scope):
        """ Ajuste de la app. Sin parámetro (borrado a mano) o con un valor desconocido: 'block'. """
        policy = self.env['ir.config_parameter'].sudo().get_str(VAT_CHECK_SCOPES[scope][0])
        return policy if policy in dict(VAT_CHECK_POLICIES) else 'block'

    def _get_vat_duplicate_partners(self, scope):
        """ Contactos principales activos del scope (clientes o proveedores), de cualquier empresa,
        con el mismo CUIT normalizado. Los contactos hijos y los que no tienen CUIT no se controlan.
        Se busca en SQL: no depende de las reglas de empresa del usuario. """
        self.ensure_one()
        normalized = self._normalize_vat_for_check(self.vat)
        if self.parent_id or not normalized:
            return self.browse()
        rank_field = VAT_CHECK_SCOPES[scope][1]
        self.flush_model(['vat', 'parent_id', 'active', rank_field])
        self.env.cr.execute(SQL("""
            SELECT id
              FROM res_partner
             WHERE parent_id IS NULL
               AND active
               AND %s > 0
               AND id != %s
               AND vat IS NOT NULL
               AND regexp_replace(upper(vat), '[^0-9A-Z]', '', 'g') = %s
             ORDER BY id
        """, SQL.identifier(rank_field), self.id, normalized))
        return self.browse([row[0] for row in self.env.cr.fetchall()]).sudo()

    def _get_vat_duplicate_message(self, scope, duplicates, warning=False):
        label = VAT_CHECK_SCOPES[scope][2]
        names = ', '.join(duplicates.mapped('display_name'))
        if warning:
            return self.env._('Atención: el CUIT %(vat)s también está cargado en el %(label)s %(names)s.',
                              vat=self.vat, label=label, names=names)
        return self.env._('El CUIT %(vat)s ya está cargado en el %(label)s %(names)s.',
                          vat=self.vat, label=label, names=names)

    @api.constrains('vat', 'parent_id')
    def _check_vat_duplicate_app(self):
        scope = self._get_vat_check_scope()
        if not scope or self._get_vat_check_policy(scope) != 'block':
            return
        for partner in self:
            duplicates = partner._get_vat_duplicate_partners(scope)
            if duplicates:
                raise ValidationError(partner._get_vat_duplicate_message(scope, duplicates))

    def _post_vat_duplicate_warning(self):
        """ Ajuste 'Avisar': deja una nota en el chatter del contacto guardado. """
        scope = self._get_vat_check_scope()
        if not scope or self._get_vat_check_policy(scope) != 'warn':
            return
        for partner in self:
            duplicates = partner._get_vat_duplicate_partners(scope)
            if duplicates:
                partner.message_post(
                    body=partner._get_vat_duplicate_message(scope, duplicates, warning=True),
                    message_type='comment', subtype_xmlid='mail.mt_note')

    @api.model_create_multi
    def create(self, vals_list):
        partners = super().create(vals_list)
        partners._post_vat_duplicate_warning()
        return partners

    def write(self, vals):
        res = super().write(vals)
        if 'vat' in vals or 'parent_id' in vals:
            self._post_vat_duplicate_warning()
        return res
