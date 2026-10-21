{
    'name': 'Proveedores',
    'version': '1.1',
    'category': 'Purchases',
    'summary': 'Tus proveedores en una app: listado, estado de cuenta, comprobantes, pagos y órdenes de compra',
    'description': """
App Proveedores: listado de proveedores con filtros, estado de cuenta de
proveedores, facturas y notas, pagos realizados, comprobantes vencidos y
órdenes de compra, con ajustes para habilitar a Compras a imputar,
desimputar y enviar el resumen por email.
""",
    'author': 'Daniel',
    'depends': ['customer_account_statement', 'purchase', 'partner_vat_check'],
    'data': [
        'security/ir.access.csv',
        'data/ir_config_parameter_data.xml',
        'views/res_partner_views.xml',
        'views/account_views.xml',
        'views/res_config_settings_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
