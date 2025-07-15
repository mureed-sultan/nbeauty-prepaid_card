from odoo import models, fields, api


class PosOrder(models.Model):
    _inherit = 'pos.order'

    receipt_ncard_data = fields.Json(string="NCard Data for Receipt", compute="_compute_receipt_ncard_data")

    @api.depends('amount_paid')
    def _compute_receipt_ncard_data(self):
        for order in self:
            txn = self.env['nbeauty.prepaid.card.transaction'].search([
                ('pos_order_id', '=', order.id),
                ('transaction_type', '=', 'pos_payment'),
                ('state', '=', 'confirmed'),
            ], limit=1, order="create_date desc")
            if txn:
                order.receipt_ncard_data = {
                    'card_no': txn.card_id.name,
                    'previous_balance': txn.balance_after + txn.amount,
                    'amount_used': txn.amount,
                    'new_balance': txn.balance_after,
                }
            else:
                order.receipt_ncard_data = False

    def export_for_printing(self):
        result = super(PosOrder, self).export_for_printing()
        result['receipt_ncard_data'] = self.receipt_ncard_data or False
        return result
