from collections import defaultdict

from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

MODES = [
    ('movements', 'Movimientos'),
    ('pending', 'Solo pendientes'),
]

PARTNER_TYPES = [
    ('customer', 'Cliente'),
    ('supplier', 'Proveedor'),
]

ACCOUNT_TYPES = {
    'customer': 'asset_receivable',
    'supplier': 'liability_payable',
}

PARTNER_LABELS = {
    'customer': 'cliente',
    'supplier': 'proveedor',
}

MAIL_TEMPLATES = {
    'customer': 'customer_account_statement.mail_template_customer_account_statement',
    'supplier': 'customer_account_statement.mail_template_supplier_account_statement',
}

DOCUMENT_TYPES = {
    'out_invoice': 'Factura',
    'out_refund': 'Nota de crédito',
    'out_receipt': 'Recibo de venta',
    'in_invoice': 'Factura de proveedor',
    'in_refund': 'Nota de crédito de proveedor',
    'in_receipt': 'Recibo de compra',
}


class CustomerAccountStatement(models.TransientModel):
    _name = 'customer.account.statement'
    _description = 'Estado de cuenta de cliente o proveedor'

    partner_type = fields.Selection(
        PARTNER_TYPES, string='Tipo', required=True, default='customer')
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True,
        domain="['|', ('is_company', '=', True), ('parent_id', '=', False)]")
    allowed_company_ids = fields.Many2many(
        'res.company', string='Empresas permitidas', compute='_compute_allowed_company_ids')
    company_ids = fields.Many2many(
        'res.company', 'customer_account_statement_company_rel', 'statement_id', 'company_id',
        string='Empresas',
        compute='_compute_company_ids', store=True, readonly=False, precompute=True)
    is_consolidated = fields.Boolean(string='Consolidado', compute='_compute_is_consolidated')
    date_from = fields.Date(string='Desde')
    date_to = fields.Date(string='Hasta', required=True, default=fields.Date.today)
    mode = fields.Selection(MODES, string='Modo', default='movements', required=True)
    # Se activa al consultar: evita calcular líneas mientras se completa el asistente previo.
    is_result = fields.Boolean(string='Consultado')
    line_ids = fields.One2many(
        'customer.account.statement.line', 'statement_id', string='Líneas',
        compute='_compute_statement', store=True, readonly=True)
    currency_total_ids = fields.One2many(
        'customer.account.statement.currency', 'statement_id', string='Saldos por moneda',
        compute='_compute_statement', store=True, readonly=True)
    can_reconcile = fields.Boolean(string='Puede imputar', compute='_compute_permissions')
    can_unreconcile = fields.Boolean(string='Puede desimputar', compute='_compute_permissions')
    can_send = fields.Boolean(string='Puede enviar por email', compute='_compute_permissions')

    @api.depends('partner_id')
    def _compute_allowed_company_ids(self):
        user_companies = self.env.user.company_ids
        for statement in self:
            partner_companies = statement.partner_id.commercial_partner_id.company_ids
            statement.allowed_company_ids = (
                partner_companies & user_companies if partner_companies else user_companies)

    @api.depends('allowed_company_ids')
    def _compute_company_ids(self):
        for statement in self:
            # _origin: en registros nuevos (precompute, onchange) los x2many traen NewId
            allowed = statement.allowed_company_ids._origin
            current = statement.company_ids._origin
            if current and current <= allowed:
                continue
            statement.company_ids = allowed

    @api.depends('company_ids')
    def _compute_is_consolidated(self):
        for statement in self:
            statement.is_consolidated = len(statement.company_ids) > 1

    @api.depends_context('uid')
    @api.depends('partner_type')
    def _compute_permissions(self):
        for statement in self:
            statement.can_reconcile = self._can_reconcile(statement.partner_type)
            statement.can_unreconcile = self._can_unreconcile(statement.partner_type)
            statement.can_send = self._can_send(statement.partner_type)

    @api.depends('is_result', 'partner_id', 'partner_type', 'company_ids', 'mode', 'date_from', 'date_to')
    def _compute_statement(self):
        for statement in self:
            line_vals = statement._prepare_lines()
            total_vals = statement._prepare_currency_totals(line_vals)
            statement.line_ids = [Command.clear()] + [Command.create(vals) for vals in line_vals]
            statement.currency_total_ids = (
                [Command.clear()] + [Command.create(vals) for vals in total_vals])

    @api.onchange('mode', 'date_from', 'date_to')
    def _onchange_dates_warning(self):
        if self.mode == 'movements' and self.date_from and self.date_to and self.date_from > self.date_to:
            return {'warning': {
                'title': self.env._('Fechas inválidas'),
                'message': self.env._('La fecha "Desde" no puede ser posterior a "Hasta".'),
            }}

    # -------------------------------------------------------------------------
    # Controles (puntos de extensión: supplier_management los amplía para Compras)
    # -------------------------------------------------------------------------

    @api.model
    def _check_partner_access(self, partner, partner_type='customer'):
        user = self.env.user
        if user.has_group('account.group_account_invoice'):
            return
        if (partner_type == 'customer'
                and user.has_group('sales_team.group_sale_salesman')
                and partner.commercial_partner_id.user_id == user):
            return
        raise AccessError(self.env._(
            'No tenés permiso para consultar el estado de cuenta de %s.',
            partner.commercial_partner_id.display_name))

    @api.model
    def _can_reconcile(self, partner_type):
        return self.env.user.has_group('account.group_account_invoice')

    @api.model
    def _can_unreconcile(self, partner_type):
        return self.env.user.has_group('account.group_account_invoice')

    @api.model
    def _can_send(self, partner_type):
        return self.env.user.has_group('account.group_account_invoice')

    def _get_partner_label(self):
        return PARTNER_LABELS[self.partner_type or 'customer']

    def _check_statement(self):
        self.ensure_one()
        self._check_partner_access(self.partner_id, self.partner_type)
        if not self.allowed_company_ids:
            raise UserError(self.env._(
                'El %s no participa en ninguna de las empresas que tenés habilitadas.',
                self._get_partner_label()))
        if not self.company_ids:
            raise UserError(self.env._('Tildá al menos una empresa.'))
        if not self.company_ids._origin <= self.allowed_company_ids._origin:
            raise UserError(self.env._(
                'El %s no participa en alguna de las empresas elegidas, '
                'o no tenés acceso a ellas.', self._get_partner_label()))
        if self.mode == 'movements' and self.date_from and self.date_from > self.date_to:
            raise UserError(self.env._('La fecha "Desde" no puede ser posterior a "Hasta".'))

    # -------------------------------------------------------------------------
    # Cálculo de líneas
    # -------------------------------------------------------------------------

    def _get_statement_companies(self):
        """ Empresas tildadas que siguen permitidas. _origin: en pantalla los x2many traen NewId. """
        return self.company_ids._origin & self.allowed_company_ids._origin

    def _get_base_domain(self, companies):
        return [
            ('partner_id', 'child_of', self.partner_id._origin.commercial_partner_id.id),
            ('company_id', 'in', companies.ids),
            ('account_id.account_type', '=', ACCOUNT_TYPES[self.partner_type]),
            ('parent_state', '=', 'posted'),
        ]

    def _get_document_type(self, move):
        if move.origin_payment_id:
            return 'Pago' if self.partner_type == 'supplier' else 'Recibo'
        if 'debit_origin_id' in move._fields and move.debit_origin_id:
            return 'Nota de débito'
        return DOCUMENT_TYPES.get(move.move_type, 'Asiento')

    def _is_reconcile_source(self, aml):
        """ True si el apunte puede imputarse a comprobantes: recibo/NC de cliente (saldo acreedor)
        o pago/NC de proveedor (saldo deudor). """
        if self.partner_type == 'supplier':
            return aml.balance > 0
        return aml.credit > 0

    def _prepare_move_line_vals(self, aml):
        company_currency = aml.company_currency_id
        foreign = aml.currency_id != company_currency
        return {
            'line_type': 'move',
            'company_id': aml.company_id.id,
            'currency_id': company_currency.id,
            'move_line_id': aml.id,
            'move_id': aml.move_id.id,
            'payment_id': aml.move_id.origin_payment_id.id,
            'document_type': self._get_document_type(aml.move_id),
            'date': aml.date,
            'date_maturity': aml.date_maturity,
            'name': aml.move_id.name,
            'debit': aml.debit,
            'credit': aml.credit,
            'balance': aml.balance,
            'original_currency_id': aml.currency_id.id if foreign else False,
            'amount_currency': aml.amount_currency if foreign else 0.0,
            'is_reconciled': aml.reconciled,
            'is_reconcile_source': self._is_reconcile_source(aml),
        }

    def _prepare_movements_lines(self, AccountMoveLine, companies):
        domain = self._get_base_domain(companies)
        balance_by_currency = defaultdict(float)
        vals_list = []
        if self.date_from:
            for company, balance in AccountMoveLine._read_group(
                    domain + [('date', '<', self.date_from)], ['company_id'], ['balance:sum']):
                balance_by_currency[company.currency_id] += balance
            for currency in companies.currency_id:
                initial = currency.round(balance_by_currency[currency])
                vals_list.append({
                    'line_type': 'initial',
                    'currency_id': currency.id,
                    'name': 'Saldo inicial',
                    'date': self.date_from,
                    'debit': max(initial, 0.0),
                    'credit': max(-initial, 0.0),
                    'balance': initial,
                    'cumulative_balance': initial,
                })
            domain += [('date', '>=', self.date_from)]
        amls = AccountMoveLine.search(
            domain + [('date', '<=', self.date_to)], order='date, move_name, id')
        for aml in amls:
            currency = aml.company_currency_id
            balance_by_currency[currency] += aml.balance
            vals = self._prepare_move_line_vals(aml)
            vals['cumulative_balance'] = currency.round(balance_by_currency[currency])
            vals_list.append(vals)
        return vals_list

    def _get_residual_at_date(self, aml):
        """ Pendiente del apunte a la fecha 'Hasta': devuelve las imputaciones posteriores. """
        residual = aml.amount_residual
        if aml.balance > 0:
            later = aml.matched_credit_ids.filtered(lambda p: p.max_date > self.date_to)
            residual += sum(later.mapped('amount'))
        else:
            later = aml.matched_debit_ids.filtered(lambda p: p.max_date > self.date_to)
            residual -= sum(later.mapped('amount'))
        return aml.company_currency_id.round(residual)

    def _prepare_pending_lines(self, AccountMoveLine, companies):
        vals_list = []
        amls = AccountMoveLine.search(
            self._get_base_domain(companies) + [('date', '<=', self.date_to)],
            order='date_maturity, date, move_name, id')
        for aml in amls:
            residual = self._get_residual_at_date(aml)
            if aml.company_currency_id.is_zero(residual):
                continue
            vals = self._prepare_move_line_vals(aml)
            overdue = (self.date_to - aml.date_maturity).days if aml.date_maturity else 0
            # En proveedores solo atrasan las facturas/ND (lo que se le debe, pendiente negativo).
            if self.partner_type == 'supplier' and residual > 0:
                overdue = 0
            vals.update({
                'amount_residual': residual,
                'days_overdue': max(overdue, 0),
            })
            vals_list.append(vals)
        return vals_list

    def _prepare_lines(self):
        """ Valores de las líneas. Vacío si todavía no se consultó o faltan datos. """
        self.ensure_one()
        companies = self._get_statement_companies()
        if not (self.is_result and self.partner_id and companies and self.date_to):
            return []
        if self.mode == 'movements' and self.date_from and self.date_from > self.date_to:
            return []
        # is_result solo se activa desde _generate_lines, después de _check_statement: el acceso
        # ya se validó. Se lee con sudo para no depender de los permisos contables del usuario
        # (vendedores, Compras) ni de las empresas activas.
        AccountMoveLine = self.env['account.move.line'].sudo()
        if self.mode == 'pending':
            vals_list = self._prepare_pending_lines(AccountMoveLine, companies)
        else:
            vals_list = self._prepare_movements_lines(AccountMoveLine, companies)
        for sequence, vals in enumerate(vals_list):
            vals['sequence'] = sequence
        return vals_list

    @api.model
    def _prepare_currency_totals(self, line_vals):
        totals = {}
        for vals in line_vals:
            total = totals.setdefault(vals['currency_id'], {
                'currency_id': vals['currency_id'],
                'initial_balance': 0.0,
                'debit': 0.0,
                'credit': 0.0,
                'final_balance': 0.0,
                'amount_residual': 0.0,
            })
            if vals['line_type'] == 'initial':
                total['initial_balance'] += vals['balance']
            else:
                total['debit'] += vals['debit']
                total['credit'] += vals['credit']
            total['final_balance'] += vals['balance']
            total['amount_residual'] += vals.get('amount_residual', 0.0)
        currencies = self.env['res.currency'].browse(totals).sorted('name')
        return [totals[currency.id] for currency in currencies]

    def _generate_lines(self):
        """ Valida y (re)calcula líneas y totales con los datos actuales de la base. """
        self.ensure_one()
        self._check_statement()
        if not self.is_result:
            self.is_result = True
        else:
            for fname in ('line_ids', 'currency_total_ids'):
                self.env.add_to_compute(self._fields[fname], self)
        self.line_ids  # dispara el cálculo pendiente

    # -------------------------------------------------------------------------
    # Datos del reporte
    # -------------------------------------------------------------------------

    def _get_report_groups(self):
        self.ensure_one()
        groups = []
        for currency in self.line_ids.currency_id.sorted('name'):
            lines = self.line_ids.filtered(lambda l: l.currency_id == currency).sorted('sequence')
            groups.append({
                'currency': currency,
                'lines': lines,
                'total_debit': sum(lines.mapped('debit')),
                'total_credit': sum(lines.mapped('credit')),
                'final_balance': sum(lines.mapped('balance')),
                'total_residual': sum(lines.mapped('amount_residual')),
            })
        return groups

    # -------------------------------------------------------------------------
    # Acciones
    # -------------------------------------------------------------------------

    def action_view(self):
        self.ensure_one()
        self._generate_lines()
        partner = self.partner_id.commercial_partner_id
        if self.partner_type == 'supplier':
            name = self.env._('Cuenta proveedor: %s', partner.display_name)
        else:
            name = self.env._('Estado de cuenta: %s', partner.display_name)
        return {
            'type': 'ir.actions.act_window',
            'name': name,
            'res_model': self._name,
            'res_id': self.id,
            'view_mode': 'form',
            'views': [(self.env.ref(
                'customer_account_statement.customer_account_statement_view_form_result').id, 'form')],
            'target': 'current',
        }

    def action_print(self):
        self.ensure_one()
        self._generate_lines()
        return self._action_print_report()

    def action_send(self):
        self.ensure_one()
        self._check_send_access()
        self._generate_lines()
        return self._action_send_mail()

    def _check_send_access(self):
        if not self._can_send(self.partner_type):
            raise AccessError(self.env._('No tenés permiso para enviar el resumen por email.'))

    def _action_print_report(self):
        """ Imprime las líneas ya calculadas. """
        self._check_partner_access(self.partner_id, self.partner_type)
        return self.env.ref(
            'customer_account_statement.action_report_customer_account_statement').report_action(self)

    def _action_send_mail(self):
        """ Envía las líneas ya calculadas. """
        self._check_send_access()
        partner = self.partner_id.commercial_partner_id
        pdf_content, _report_type = self.env['ir.actions.report']._render_qweb_pdf(
            'customer_account_statement.action_report_customer_account_statement', self.ids)
        attachment = self.env['ir.attachment'].create({
            'name': f'Resumen de cuenta - {partner.name} - {self.date_to}.pdf',
            'type': 'binary',
            'raw': pdf_content,
            'mimetype': 'application/pdf',
            'res_model': 'mail.compose.message',
            'res_id': 0,
        })
        template = self.env.ref(MAIL_TEMPLATES[self.partner_type])
        return {
            'type': 'ir.actions.act_window',
            'name': self.env._('Enviar resumen de cuenta'),
            'res_model': 'mail.compose.message',
            'view_mode': 'form',
            'views': [(False, 'form')],
            'target': 'new',
            'context': {
                'default_model': 'res.partner',
                'default_res_ids': partner.ids,
                'default_composition_mode': 'comment',
                'default_template_id': template.id,
                'default_attachment_ids': attachment.ids,
                'force_email': True,
            },
        }
