{
    'name': 'Estado de cuenta de clientes',
    'version': '1.0',
    'category': 'Accounting',
    'summary': 'Consultá, imprimí, enviá e imputá la cuenta corriente de tus clientes',
    'description': """
Estado de cuenta de clientes por empresa o consolidado por moneda:
movimientos con saldo acumulado, comprobantes pendientes, detalle e
imputación de recibos y notas de crédito, resumen en PDF y envío por email.
""",
    'author': 'Daniel',
    'depends': ['account', 'sales_team'],
    'data': [
        'security/ir.access.csv',
        'data/mail_template_data.xml',
        'report/account_statement_report.xml',
        'report/account_statement_templates.xml',
        'wizard/account_statement_wizard_views.xml',
        'wizard/account_statement_line_views.xml',
        'wizard/account_statement_reconcile_views.xml',
        'views/account_partial_reconcile_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'license': 'LGPL-3',
}
