from odoo import api, models

from ..models.stock_control_manual_move import stock_control_location_qty


class ReportStockControlCountSheet(models.AbstractModel):
    _name = 'report.stock_control.report_count_sheet'
    _description = 'Planilla de conteo'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.control.inventory'].browse(docids)
        show_theoretical = docs[:1]._sheet_show_theoretical()
        theoretical = {}
        if show_theoretical:
            for line in docs.line_ids:
                if line.inventory_id.theoretical_mode == 'on_start' or line.is_applied:
                    theoretical[line.id] = line.theoretical_qty
                else:
                    theoretical[line.id] = stock_control_location_qty(line.product_id, line.location_id)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.control.inventory',
            'docs': docs,
            'groups': {doc.id: doc._get_sheet_groups() for doc in docs},
            'show_theoretical': show_theoretical,
            'theoretical': theoretical,
        }


class ReportStockControlDifferences(models.AbstractModel):
    _name = 'report.stock_control.report_differences'
    _description = 'Informe de diferencias de control de inventario'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.control.inventory'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.control.inventory',
            'docs': docs,
            'groups': {doc.id: doc._get_sheet_groups() for doc in docs},
            'events': {doc.id: doc.event_ids.sorted(lambda e: (e.date, e.id)) for doc in docs},
        }


class ReportStockControlKardex(models.AbstractModel):
    _name = 'report.stock_control.report_kardex'
    _description = 'Ficha por producto (kardex)'

    @api.model
    def _get_report_values(self, docids, data=None):
        docs = self.env['stock.control.kardex.wizard'].browse(docids)
        return {
            'doc_ids': docids,
            'doc_model': 'stock.control.kardex.wizard',
            'docs': docs,
            'kardex': {doc.id: doc._get_kardex_data() for doc in docs},
        }
