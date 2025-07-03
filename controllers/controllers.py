# controllers/main.py
from odoo import http
from odoo.http import request

class NCardPOSController(http.Controller):
    @http.route('/ncard/validate', type='json', auth='user')
    def validate_ncard(self, card_number):
        card_number = card_number.replace(" ", "")
        card = request.env['nbeauty.prepaid.card'].sudo().search([('name', '=', card_number)], limit=1)

        if not card or card.state != 'active' or card.expiry_date < fields.Date.today() or card.balance <= 0:
            return {'valid': False}

        return {
            'valid': True,
            'card_id': card.id,
            'balance': card.balance
        }
