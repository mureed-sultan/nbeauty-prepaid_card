from odoo import models, fields, api
from odoo.exceptions import UserError


class NBeautyPrepaidCardTopupWizard(models.TransientModel):
    _name = 'nbeauty.prepaid.card.topup.wizard'
    _description = 'Top-Up Prepaid Card'

    search_type = fields.Selection([
        ('name', 'Customer Name'),
        ('phone', 'Customer Phone'),
        ('card_no', 'Card Number'),
    ], string="Search By", required=True)

    search_value = fields.Char(string="Search For", required=True)

    card_id = fields.Many2one('nbeauty.prepaid.card', string="Matched Card", readonly=True)
    customer_id = fields.Many2one(related='card_id.customer_id', store=True, readonly=True)
    customer_phone = fields.Char(
        string="Customer Phone",
        related='card_id.customer_id.mobile',
        store=True,
        readonly=True,
    )
    current_balance = fields.Float(related='card_id.balance', readonly=True)

    topup_amount = fields.Float(string="Top-Up Amount")
    description = fields.Char(string="Description")

    @api.onchange('search_type')
    def _onchange_search_type(self):
        self.search_value = ""

    def action_fetch_card(self):
        self.ensure_one()
        val = self.search_value.strip()
        domain = []

        if self.search_type == 'name':
            domain = [('customer_id.name', 'ilike', val)]
        elif self.search_type == 'phone':
            domain = [('customer_id.phone', 'ilike', val)]
        elif self.search_type == 'card_no':
            domain = [('name', '=', val.replace(" ", ""))]

        card = self.env['nbeauty.prepaid.card'].search(domain, limit=1)

        if not card:
            raise UserError("No card found matching the given criteria.")

        self.card_id = card.id

    def action_topup(self):
        self.ensure_one()
        if not self.card_id:
            raise UserError("Please fetch a card before updating.")
        if self.topup_amount <= 0:
            raise UserError("Amount must be greater than 0.")

        # Call card method to update balance and create transaction
        self.card_id.create_topup_transaction(
            card_id=self.card_id.id,
            amount=self.topup_amount,
            description=self.description or "Top-Up"
        )

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Top-Up Successful',
                'message': f"{self.topup_amount:.2f} added to card {self.card_id.name}",
                'sticky': False,
            }
        }
