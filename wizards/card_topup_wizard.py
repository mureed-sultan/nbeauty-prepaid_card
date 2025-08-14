import requests
import json
import logging
from odoo import models, fields, api
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class NBeautyPrepaidCardTopupWizard(models.TransientModel):
    _name = 'nbeauty.prepaid.card.topup.wizard'
    _description = 'Top-Up Prepaid Card'

    # SELECT WHICH DROPDOWN TO USE
    search_type = fields.Selection([
        ('name', 'Customer Name'),
        ('phone', 'Customer Phone'),
        ('card_no', 'Card Number'),
    ], string="Search By", required=True)

    # Legacy text box (not used now, but kept in case you need it later)
    search_value = fields.Char(string="Search For")

    # DROPDOWNS
    customer_selection_id = fields.Many2one(
        'res.partner',
        string="Select Customer",
        domain="[('customer_rank', '>', 0)]",
        help="Choose the customer by name."
    )

    customer_phone_selection_id = fields.Many2one(
        'res.partner',
        string="Select Customer (Phone)",
        domain="[('customer_rank', '>', 0)]",
        help="Choose the customer by phone number. The dropdown shows the phone if context flag is set."
    )

    card_selection_id = fields.Many2one(
        'nbeauty.prepaid.card',
        string="Select Card Number",
        help="Choose the card by its number."
        # NOTE: Do NOT put domain with 'active' unless your card model has an active field
        # domain=[('active', '=', True)]
    )

    # RESOLVED/DERIVED FIELDS
    card_id = fields.Many2one('nbeauty.prepaid.card', string="Matched Card", readonly=True)
    customer_id = fields.Many2one(related='card_id.customer_id', store=True, readonly=True)
    customer_phone = fields.Char(
        string="Customer Phone",
        related='card_id.customer_id.mobile',
        store=True,
        readonly=True,
    )
    current_balance = fields.Float(related='card_id.balance', readonly=True)
    bonus_amount = fields.Monetary(
        string="Bonus Amount",
        compute="_compute_bonus",
        readonly=True,
        store=True
    )
    currency_id = fields.Many2one('res.currency', related='card_id.currency_id', store=True)

    topup_amount = fields.Float(string="Top-Up Amount")
    description = fields.Char(string="Description")
    display_name = fields.Char(string='Display Name', compute='_compute_display_name', store=True)

    # ---- COMPUTES / ONCHANGES ----
    @api.depends('card_id')
    def _compute_display_name(self):
        for rec in self:
            rec.display_name = f"Card Top-Up: {rec.card_id.name or 'No Card'}"

    @api.onchange('search_type')
    def _onchange_search_type(self):
        # Reset UI selections when user switches the search mode
        self.search_value = ""
        self.customer_selection_id = False
        self.customer_phone_selection_id = False
        self.card_selection_id = False
        self.card_id = False

    @api.depends('topup_amount', 'card_id.card_type_id.bonus_percentage')
    def _compute_bonus(self):
        for rec in self:
            if rec.card_id and rec.card_id.card_type_id:
                percent = rec.card_id.card_type_id.bonus_percentage or 0.0
                rec.bonus_amount = round((rec.topup_amount or 0.0) * percent / 100, 2)
            else:
                rec.bonus_amount = 0.0

    # ---- ACTIONS ----
    def action_fetch_card(self):
        self.ensure_one()

        if self.search_type == 'name':
            if not self.customer_selection_id:
                raise UserError("Please select a customer.")
            domain = [('customer_id', '=', self.customer_selection_id.id)]

        elif self.search_type == 'phone':
            if not self.customer_phone_selection_id:
                raise UserError("Please select a customer by phone.")
            domain = [('customer_id', '=', self.customer_phone_selection_id.id)]

        elif self.search_type == 'card_no':
            if not self.card_selection_id:
                raise UserError("Please select a card.")
            domain = [('id', '=', self.card_selection_id.id)]

        else:
            raise UserError("Invalid search type.")

        card = self.env['nbeauty.prepaid.card'].search(domain, limit=1)
        if not card:
            raise UserError("No card found matching the given criteria.")

        self.card_id = card.id

    def action_topup(self):
        self.ensure_one()

        if not self.card_id:
            raise UserError("No card selected.")
        if self.topup_amount <= 0:
            raise UserError("Top-up amount must be greater than 0.")

        card_type = self.card_id.card_type_id
        bonus = 0.0
        if card_type:
            bonus = round((self.topup_amount * (card_type.bonus_percentage or 0.0)) / 100, 2)

        previous_balance = round(self.card_id.balance, 2)

        # Top-Up Transaction
        self.env['nbeauty.prepaid.card.transaction'].create_topup_transaction(
            card_id=self.card_id.id,
            amount=self.topup_amount,
            description=self.description or 'Top-Up',
            branch_id=getattr(self.card_id, 'branch_id', False).id if getattr(self.card_id, 'branch_id', False) else False
        )

        # Bonus Transaction
        if bonus > 0:
            self.card_id.balance += bonus
            self.env['nbeauty.prepaid.card.transaction'].create({
                'card_id': self.card_id.id,
                'transaction_type': 'bonus',
                'amount': bonus,
                'balance_after': self.card_id.balance,
                'description': 'Bonus Credit',
                'branch_id': getattr(self.card_id, 'branch_id', False).id if getattr(self.card_id, 'branch_id', False) else False,
            })

        # WhatsApp notification
        if self.customer_phone:
            phone_number = self.customer_phone.replace("+", "").replace(" ", "")
            message_body = (
                f"Dear {self.customer_id.name},\n\n"
                f"Your NCard ({self.card_id.name}) has been topped up.\n"
                f"Top-up Amount: {round(self.topup_amount, 2)} AED\n"
                f"Bonus Amount: {round(bonus, 2)} AED\n"
                f"Previous Balance: {round(previous_balance, 2)} AED\n"
                f"New Balance: {round(self.card_id.balance, 2)} AED\n\n"
                f"Thank you for using our services."
            )
            payload = json.dumps({
                "app-key": "d6342231-fbe0-4bf2-b4b9-9475ccb202be",
                "auth-key": "2d1e0678a72544dbaaf5fc31d2e8b9ec5015c6be085fe44b47",
                "destination_number": phone_number,
                "template_id": "24932727729662154",
                "device_id": "67cfa013e9f65c8638a8fd0b",
                "variables": [
                    self.customer_id.name,
                    self.card_id.name,
                    str(round(self.topup_amount, 2)),
                    str(round(bonus, 2)),
                    str(round(previous_balance, 2)),
                    str(round(self.card_id.balance, 2))
                ],
                "button_variable": [],
                "media": "",
                "message": message_body
            })
            headers = {'Content-Type': 'application/json'}
            try:
                response = requests.post(
                    "https://web.wabridge.com/api/createmessage",
                    headers=headers,
                    data=payload,
                    timeout=10
                )
                _logger.info("WA Bridge Response: %s %s", response.status_code, response.text)
            except Exception as e:
                _logger.warning("WA Bridge Exception: %s", e)

        return self.action_print_topup_receipt()

    def action_print_topup_receipt(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'nbeauty_prepaid_card.report_topup_receipt_template',
            'report_type': 'qweb-html',
            'model': 'nbeauty.prepaid.card.topup.wizard',
            'context': {
                'discard_logo_check': True,
                'force_report_rendering': True
            }
        }

    def name_get(self):
        """Keep the wizard's own name_get normal (used for display_name)."""
        return [(record.id, record.display_name or 'Card Top-Up') for record in self]


# ------------------------------------------------------------
# Extend res.partner to show phone in dropdown when context set
# ------------------------------------------------------------
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def name_get(self):
        res = []
        for partner in self:
            display_name = partner.name
            if partner.mobile:
                display_name = f"{partner.mobile} - {partner.name}"
            elif partner.phone:
                display_name = f"{partner.phone} - {partner.name}"
            res.append((partner.id, display_name))
        return res