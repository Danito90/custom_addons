{
    'name': 'Visitas a clientes',
    'version': '1.1',
    'category': 'Sales',
    'summary': 'Planificá y registrá visitas a clientes',
    'description': """
Registro de visitas a clientes: planificación, resultado, próxima visita
y seguimiento con chatter y actividades.
""",
    'author': 'Daniel',
    'depends': ['mail'],
    'data': [
        'security/ir.access.csv',
        'data/ir_sequence_data.xml',
        'views/customer_visit_views.xml',
        'views/res_partner_views.xml',
        'views/menus.xml',
    ],
    'application': True,
    'license': 'LGPL-3',
}
