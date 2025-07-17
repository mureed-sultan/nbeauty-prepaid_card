from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # This field will store the NCard transaction details
    receipt_ncard_data = fields.Json(string="NCard Data for Receipt", help="JSON data for NCard transaction details on the receipt.")

    @api.model
    def api_set_ncard_data(self, order_uuid, ncard_data):
        pos_order = self.env['pos.order'].search([('uuid', '=', order_uuid)], limit=1)
        if not pos_order:
            print("!!! Order not found for UUID:", order_uuid)
            return False
        pos_order.write({'receipt_ncard_data': ncard_data})
        return True

    @api.model
    def _order_fields(self, ui_order):
        res = super()._order_fields(ui_order)
        if ui_order.get('ncard_data'):
            res['receipt_ncard_data'] = ui_order['ncard_data']
        return res
    def export_for_printing(self):
        result = super().export_for_printing()
        result['receipt_ncard_data'] = self.receipt_ncard_data or None
        return result
