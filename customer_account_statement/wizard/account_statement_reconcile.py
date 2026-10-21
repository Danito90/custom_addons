from odoo import Command, api, fields, models
from odoo.exceptions import AccessError, UserError

from .account_statement_wizard import ACCOUNT_TYPES, PARTNER_TYPES


class CustomerAccountStatementReconcile(models.TransientModel):
    _name = 'customer.account.statement.reconcile'
    _description = 'Imputación de crédito de cliente o proveedor'

    statement_id = fields.Many2one('customer.account.statement', string='Estado de cuenta')
    # Origen de la imputación: recibo/NC de cliente (pendiente negativo) o pago/NC de proveedor
    # (pendiente positivo). El nombre del campo se conserva por compatibilidad.
    credit_line_id = fields.Many2one(
        'account.move.line', string='Crédito', required=True,
        domain="[('account_id.account_type', 'in', ('asset_receivable', 'liability_payable'))]")
    partner_type = fields.Selection(
        PARTNER_TYPES, string='Tipo', compute='_compute_partner_type', store=True, precompute=True)
    partner_id = fields.Many2one(
        'res.partner', string='Cliente', required=True,
        compute='_compute_partner_id', store=True, precompute=True)
    company_id = fields.Many2one(related='credit_line_id.company_id')
    company_currency_id = fields.Many2one(related='credit_line_id.company_currency_id')
    available_amount = fields.Monetary(
        string='Disponible', currency_field='company_currency_id',
        compute='_compute_available_amount', store=True, precompute=True)
    line_ids = fields.One2many(
        'customer.account.statement.reconcile.line', 'reconcile_id', string='Comprobantes',
        compute='_compute_line_ids', store=True, readonly=False, precompute=True)

    @api.depends('statement_id.partner_type', 'credit_line_id')
    def _compute_partner_type(self):
        for wizard in self:
            if wizard.statement_id:
                wizard.partner_type = wizard.statement_id.partner_type
            elif wizard.credit_line_id.account_id.account_type == 'liability_payable':
                wizard.partner_type = 'supplier'
            else:
                wizard.partner_type = 'customer'

    @api.depends('credit_line_id')
    def _compute_partner_id(self):
        for wizard in self:
            wizard.partner_id = wizard.credit_line_id.partner_id.commercial_partner_id

    @api.depends('credit_line_id')
    def _compute_available_amount(self):
        for wizard in self:
            wizard.available_amount = abs(wizard.credit_line_id.amount_residual)

    def _get_target_sign(self):
        """ Signo del pendiente de los comprobantes a cancelar: facturas/ND de cliente (+) o de
        proveedor (−). El origen tiene el signo contrario. """
        return -1 if self.partner_type == 'supplier' else 1

    @api.depends('credit_line_id', 'partner_type')
    def _compute_line_ids(self):
        for wizard in self:
            credit = wizard.credit_line_id
            commands = [Command.clear()]
            if credit:
                company_currency = credit.company_currency_id
                residual_operator = '<' if wizard._get_target_sign() < 0 else '>'
                debits = self.env['account.move.line'].search([
                    ('partner_id', 'child_of', credit.partner_id.commercial_partner_id.id),
                    ('company_id', '=', credit.company_id.id),
                    ('account_id', '=', credit.account_id.id),
                    ('parent_state', '=', 'posted'),
                    ('reconciled', '=', False),
                    ('amount_residual', residual_operator, 0),
                ], order='date_maturity, date, id')
                commands += [Command.create({
                    'debit_line_id': debit.id,
                    'amount_residual': abs(debit.amount_residual),
                    'allow_partial': (debit.currency_id == company_currency
                                      and credit.currency_id == company_currency),
                }) for debit in debits]
            wizard.line_ids = commands

    @api.onchange('line_ids')
    def _onchange_line_ids(self):
        """ Propone para cada comprobante marcado el mínimo entre su pendiente y lo que queda disponible. """
        remaining = self.available_amount
        for line in self.line_ids:
            if not line.selected:
                line.amount_to_apply = 0.0
                continue
            if not line.amount_to_apply or not line.allow_partial:
                line.amount_to_apply = max(min(line.amount_residual, remaining), 0.0)
            remaining -= line.amount_to_apply

    def _check_lines(self, lines):
        """ El origen y los comprobantes son del mismo cliente/proveedor, empresa y cuenta, con el
        signo esperado. Protege la imputación aunque los datos lleguen armados por RPC. """
        credit = self.credit_line_id
        sign = self._get_target_sign()
        currency = self.company_currency_id
        partner = self.partner_id.commercial_partner_id
        if (credit.account_id.account_type != ACCOUNT_TYPES[self.partner_type]
                or credit.parent_state != 'posted'
                or credit.partner_id.commercial_partner_id != partner):
            raise UserError(self.env._('El crédito %s no se puede imputar desde este estado de cuenta.',
                                       credit.move_id.name))
        if credit.reconciled or currency.compare_amounts(-sign * credit.amount_residual, 0.0) <= 0:
            raise UserError(self.env._('El crédito %s no tiene saldo disponible.', credit.move_id.name))
        for debit in lines.debit_line_id:
            if (debit.company_id != credit.company_id
                    or debit.account_id != credit.account_id
                    or debit.parent_state != 'posted'
                    or debit.partner_id.commercial_partner_id != partner
                    or debit.reconciled
                    or currency.compare_amounts(sign * debit.amount_residual, 0.0) <= 0):
                raise UserError(self.env._(
                    'El comprobante %s no se puede imputar con este crédito.', debit.move_id.name))

    def _check_amounts(self, lines):
        currency = self.company_currency_id
        credit = self.credit_line_id
        for line in lines:
            if currency.compare_amounts(line.amount_to_apply, 0.0) <= 0:
                raise UserError(self.env._(
                    'El importe a imputar en %s debe ser mayor a cero.', line.move_id.name))
            if currency.compare_amounts(line.amount_to_apply, abs(line.debit_line_id.amount_residual)) > 0:
                raise UserError(self.env._(
                    'El importe a imputar en %s supera su pendiente.', line.move_id.name))
        if currency.compare_amounts(sum(lines.mapped('amount_to_apply')), abs(credit.amount_residual)) > 0:
            raise UserError(self.env._('La suma a imputar supera el disponible del crédito.'))

    def _reconcile_partial_amount(self, target_line, source_line, amount):
        """ Imputa un importe menor al pendiente de ambos apuntes (solo moneda de la empresa).

        Odoo no tiene API pública para esto: se arma el parcial con
        `_prepare_reconciliation_single_partial` limitando el residual del comprobante destino al
        importe pedido. En clientes el destino es el apunte deudor (residual `amount`); en
        proveedores es el acreedor (residual `-amount`). Como ambos apuntes quedan con pendiente,
        nunca se genera conciliación total.
        """
        AccountMoveLine = self.env['account.move.line']
        amls = target_line + source_line
        source_values = {
            'aml': source_line,
            'amount_residual': source_line.amount_residual,
            'amount_residual_currency': source_line.amount_residual_currency,
            'parent_state': source_line.parent_state,
        }
        limited = amount * self._get_target_sign()
        target_values = {
            'aml': target_line,
            'amount_residual': limited,
            'amount_residual_currency': limited,
            'parent_state': target_line.parent_state,
        }
        if self.partner_type == 'supplier':
            debit_values, credit_values = source_values, target_values
        else:
            debit_values, credit_values = target_values, source_values
        pre_hook_data = amls._reconcile_pre_hook()
        container = {'records': amls.move_id}
        with amls.move_id._check_balanced(container), amls.move_id._sync_dynamic_lines(container):
            results = AccountMoveLine.with_context(no_exchange_difference=True)._prepare_reconciliation_single_partial(
                debit_values, credit_values)
            partial = self.env['account.partial.reconcile'].create(results['partial_values'])
        if (any(amls.company_id.mapped('tax_exigibility'))
                and not self.env.context.get('no_cash_basis')):
            partial._create_tax_cash_basis_moves()
        amls._reconcile_post_hook(pre_hook_data)

    def _check_reconcile_access(self):
        Statement = self.env['customer.account.statement']
        Statement._check_partner_access(self.partner_id, self.partner_type)
        if not Statement._can_reconcile(self.partner_type):
            raise AccessError(self.env._('No tenés permiso para imputar.'))

    def action_reconcile(self):
        self.ensure_one()
        self._check_reconcile_access()
        lines = self.line_ids.filtered('selected')
        if not lines:
            raise UserError(self.env._('Marcá al menos un comprobante para imputar.'))
        self._check_lines(lines)
        self._check_amounts(lines)
        currency = self.company_currency_id
        credit = self.credit_line_id
        for line in lines.sorted(lambda l: (l.date_maturity or l.debit_line_id.date, l.id)):
            if credit.reconciled:
                break
            debit = line.debit_line_id
            full_possible = min(abs(debit.amount_residual), abs(credit.amount_residual))
            if not line.allow_partial or currency.compare_amounts(line.amount_to_apply, full_possible) >= 0:
                (debit + credit).reconcile()
            else:
                self._reconcile_partial_amount(debit, credit, line.amount_to_apply)
        if self.statement_id:
            self.statement_id._generate_lines()
        return {'type': 'ir.actions.act_window_close'}


class CustomerAccountStatementReconcileLine(models.TransientModel):
    _name = 'customer.account.statement.reconcile.line'
    _description = 'Comprobante a imputar'
    _order = 'id'

    reconcile_id = fields.Many2one(
        'customer.account.statement.reconcile', required=True, ondelete='cascade')
    selected = fields.Boolean(string='Imputar')
    # Destino de la imputación: factura/ND de cliente o de proveedor. Importes en valor absoluto.
    debit_line_id = fields.Many2one('account.move.line', string='Apunte', required=True)
    move_id = fields.Many2one(related='debit_line_id.move_id', string='Comprobante')
    date = fields.Date(related='debit_line_id.date', string='Fecha')
    date_maturity = fields.Date(related='debit_line_id.date_maturity', string='Vencimiento')
    original_currency_id = fields.Many2one(related='debit_line_id.currency_id', string='Moneda')
    currency_id = fields.Many2one(related='reconcile_id.company_currency_id')
    amount_residual = fields.Monetary(string='Pendiente')
    amount_to_apply = fields.Monetary(string='Importe a imputar')
    allow_partial = fields.Boolean(string='Permite importe parcial')
