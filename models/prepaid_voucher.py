from odoo import models, fields, api
from datetime import date

class NBeautyVoucher(models.Model):
    _name = 'nbeauty.prepaid.card.voucher'
    _description = 'Prepaid Reward Voucher'
    _order = 'issued_date desc'

    name = fields.Char(string="Voucher Code", required=True, copy=False, default='New')
    card_id = fields.Many2one('nbeauty.prepaid.card', required=True, ondelete='cascade')
    customer_id = fields.Many2one(related='card_id.customer_id', store=True)
    amount = fields.Float(string="Value", required=True)
    voucher_type = fields.Selection([
        ('product', 'Product Discount'),
        ('service', 'Free Service'),
    ], required=True)
    description = fields.Text()
    issued_date = fields.Date(default=fields.Date.today)
    expiry_date = fields.Date()
    redeemed = fields.Boolean(default=False)
    redeemed_date = fields.Date()
    pos_order_id = fields.Many2one('pos.order', string="Redeemed POS Order")

    @api.model
    def create(self, vals):
        if vals.get('name') == 'New':
            seq = self.env['ir.sequence'].next_by_code('nbeauty.voucher') or 'VOUCHER0001'
            vals['name'] = seq
        return super().create(vals)

    def action_mark_redeemed(self):
        for voucher in self:
            if voucher.redeemed:
                continue
            voucher.redeemed = True
            voucher.redeem_date = fields.Date.today()