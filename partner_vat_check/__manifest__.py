{
    'name': 'Control de CUIT repetido',
    'version': '1.0',
    'category': 'Hidden',
    'summary': 'Bloquea o avisa CUIT repetidos al dar de alta clientes y proveedores desde sus apps',
    'description': """
Control de CUIT repetido para las apps Clientes y Proveedores: cada app
tiene su ajuste (Bloquear, Avisar o No controlar) y compara solo contra
clientes o solo contra proveedores activos, con el CUIT normalizado.
""",
    'author': 'Daniel',
    # account: define customer_rank y supplier_rank, que se usan para comparar.
    'depends': ['account'],
    'data': [
        'data/ir_config_parameter_data.xml',
    ],
    'license': 'LGPL-3',
}
