from odoo import models, fields, api

class PosOrder(models.Model):
    _inherit = 'pos.order'

    # This field will store the NCard transaction details
    receipt_ncard_data = fields.Json(string="NCard Data for Receipt", help="JSON data for NCard transaction details on the receipt.")

    @api.model
    def api_set_ncard_data(self, order_uuid, ncard_data):
        """
        Sets the NCard transaction data on the POS order for receipt printing.
        This method is explicitly called from the frontend after successful NCard payment processing.
        """
        print("\n\n========== api_set_ncard_data CALLED (Backend) ==========")
        print(f"order_uuid: {order_uuid}")
        print(f"ncard_data received: {ncard_data}")
        print("================================================\n\n")

        pos_order = self.env['pos.order'].search([('uuid', '=', order_uuid)], limit=1)
        if not pos_order:
            print("!!! Order not found for UUID:", order_uuid)
            return False

        # Update the JSON field directly using .write() for persistence
        # This is the crucial step to save the data to the database.
        pos_order.write({'receipt_ncard_data': ncard_data})
        print(f"Receipt NCard data successfully written to order ID {pos_order.id}")
        return True

    @api.model
    def _order_fields(self, ui_order):
        """
        This method is called when the POS sends the order data to the backend for creation/validation.
        While 'ncard_data' might be present in ui_order from export_as_JSON,
        we are explicitly using api_set_ncard_data for persistence after payment.
        This method ensures the base order fields are processed.
        """
        res = super()._order_fields(ui_order)
        # We are not relying on this for receipt_ncard_data persistence in this flow,
        # as api_set_ncard_data is called separately.
        return res

    def export_for_printing(self):
        """
        Exports order data for printing, ensuring the persisted NCard data is included.
        This method is called both for immediate POS receipt printing (via proxy)
        and for reprinting receipts from the backend.
        """
        print("\n\n========== Python export_for_printing CALLED (Backend) ==========")
        print(f"Order UUID: {self.uuid}")
        print(f"Order ID: {self.id}")
        # Retrieve the receipt_ncard_data directly from the current pos.order record (persisted in DB)
        print(f"receipt_ncard_data from pos.order (persisted in DB): {self.receipt_ncard_data}")
        print("================================================\n\n")

        result = super().export_for_printing()
        # Ensure the persisted data is included in the result dictionary for the receipt template
        result['receipt_ncard_data'] = self.receipt_ncard_data or None

        print("\n\n========== Python export_for_printing RETURNING (Backend) ==========")
        print(f"Result dict for printing: {result}")
        print("====================================================\n\n")
        return result
