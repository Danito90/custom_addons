{
    'name': 'Clientes',
    'version': '1.0',
    'category': 'Sales',
    'summary': 'Tus clientes en una app: listado, vendedores, estado de cuenta, comprobantes y visitas',
    'description': """
App Clientes: listado de clientes con filtros y asignación de vendedores,
estado de cuenta, facturas y notas, pagos recibidos, comprobantes vencidos
y visitas, con un ajuste para que los vendedores vean solo sus clientes.
""",
    'author': 'Daniel',
    'depends': ['customer_account_statement', 'customer_visit'],
    'data': [
        'security/ir.access.csv',
        'views/res_partner_views.xml',
        'views/account_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/assign_salesman_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
