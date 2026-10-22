from odoo import fields, models

from .stock_control_inventory import THEORETICAL_MODES


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_control_theoretical_mode = fields.Selection(
        THEORETICAL_MODES, string='Comparar contra',
        config_parameter='stock_control.theoretical_mode')
    # Parámetro estándar de Inventario: lo usan también la "Hoja de conteo" y "Solicitar un conteo".
    stock_control_sheet_show_theoretical = fields.Boolean(
        'Mostrar cantidad teórica en la planilla',
        config_parameter='stock.show_expected_quantity_count')
