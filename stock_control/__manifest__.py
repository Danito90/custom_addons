{
    'name': 'Control de inventario',
    'version': '1.0',
    'category': 'Inventory/Inventory',
    'summary': 'Movimientos de stock con motivo, controles de conteo cerrados y auditoría de stock',
    'description': """
App Control de inventario sobre el Inventario de Odoo: entradas y salidas
manuales con motivo, controles de inventario por depósito y categoría con
planilla de conteo, ajuste al guardar y bloqueo del control guardado (solo un
administrador lo reabre), y auditoría de movimientos, ficha por producto
(kardex) y diferencias de controles.
""",
    'author': 'Daniel',
    'depends': ['stock', 'purchase_stock', 'sale_stock', 'mail'],
    'data': [
        'security/stock_control_security.xml',
        'security/ir.access.csv',
        'data/ir_config_parameter_data.xml',
        'data/ir_sequence_data.xml',
        'data/stock_control_reason_data.xml',
        'report/stock_control_reports.xml',
        'report/report_count_sheet.xml',
        'report/report_differences.xml',
        'report/report_kardex.xml',
        'views/stock_control_reason_views.xml',
        'views/stock_move_views.xml',
        'views/stock_control_manual_move_views.xml',
        'views/stock_control_inventory_views.xml',
        'views/product_views.xml',
        'views/res_config_settings_views.xml',
        'wizard/stock_control_reopen_wizard_views.xml',
        'wizard/stock_control_kardex_wizard_views.xml',
        'views/menus.xml',
    ],
    'uninstall_hook': '_uninstall_hook',
    'application': True,
    'license': 'LGPL-3',
}
