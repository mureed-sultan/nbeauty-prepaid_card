from odoo import models, fields, api
from odoo.exceptions import UserError


class PosPaymentMethod(models.Model):
    _inherit = 'pos.payment.method'

    is_n_card = fields.Boolean("Is N Card Payment", default=False)
    ncard_type_id = fields.Many2one('nbeauty.prepaid.card.type', string="N Card Type")

    def validate_ncard_payment(self, card_number, customer_id=False):
        """ Validate N Card payment """
        self.ensure_one()

        Card = self.env['nbeauty.prepaid.card']
        card = Card.search([('name', '=', card_number.replace(" ", ""))], limit=1)

        if not card:
            return {
                'success': False,
                'message': 'Card not found. Please check the card number.',
                'card_data': None
            }

        if card.state != 'active':
            return {
                'success': False,
                'message': 'Card is not active. Please contact support.',
                'card_data': None
            }

        if card.expiry_date and card.expiry_date < fields.Date.today():
            return {
                'success': False,
                'message': 'Card has expired. Please renew your card.',
                'card_data': None
            }

        if customer_id and card.customer_id.id != customer_id:
            return {
                'success': False,
                'message': 'Card does not belong to this customer.',
                'card_data': None
            }

        return {
            'success': True,
            'message': 'Card validated successfully',
            'card_data': {
                'id': card.id,
                'balance': card.balance,
                'customer_name': card.customer_id.name,
                'expiry_date': card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else 'N/A'
            }
        }