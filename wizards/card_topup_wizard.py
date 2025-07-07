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
    bonus_amount = fields.Monetary(
        string="Bonus Amount",
        compute="_compute_bonus",
        readonly=True,
        store=True
    )
    currency_id = fields.Many2one('res.currency', related='card_id.currency_id', store=True)

    topup_amount = fields.Float(string="Top-Up Amount")
    description = fields.Char(string="Description")

    @api.onchange('search_type')
    def _onchange_search_type(self):
        self.search_value = ""

    @api.depends('topup_amount', 'card_id.card_type_id.bonus_percentage')
    def _compute_bonus(self):
        for rec in self:
            if rec.card_id and rec.card_id.card_type_id:
                percent = rec.card_id.card_type_id.bonus_percentage or 0.0
                rec.bonus_amount = (rec.topup_amount or 0.0) * percent / 100
            else:
                rec.bonus_amount = 0.0

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
            raise UserError("No card selected.")

        if self.topup_amount <= 0:
            raise UserError("Top-up amount must be greater than 0.")

        card_type = self.card_id.card_type_id
        bonus = 0.0
        if card_type:
            bonus = (self.topup_amount * (card_type.bonus_percentage or 0.0)) / 100

        # Create top-up transaction
        self.env['nbeauty.prepaid.card.transaction'].create_topup_transaction(
            card_id=self.card_id.id,
            amount=self.topup_amount,
            description=self.description or 'Top-Up',
            branch_id=getattr(self.card_id, 'branch_id', False).id if getattr(self.card_id, 'branch_id',
                                                                              False) else False
        )

        # Create bonus transaction if applicable
        if bonus > 0:
            self.card_id.balance += bonus  # Update balance manually
            self.env['nbeauty.prepaid.card.transaction'].create({
                'card_id': self.card_id.id,
                'transaction_type': 'bonus',
                'amount': bonus,
                'balance_after': self.card_id.balance,
                'description': 'Bonus Credit',
                'branch_id': getattr(self.card_id, 'branch_id', False).id if getattr(self.card_id, 'branch_id',
                                                                                     False) else False,
            })

        # Show notification, clear fields
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Success',
                'message': 'Top-up and bonus applied successfully.',
                'type': 'success',
                'sticky': False,
            }
        }

    @api.onchange('topup_amount', 'card_id')
    def _onchange_bonus_amount(self):
        for rec in self:
            if rec.card_id and rec.card_id.card_type_id:
                percent = rec.card_id.card_type_id.bonus_percentage or 0.0
                rec.bonus_amount = (rec.topup_amount or 0.0) * percent / 100
            else:
                rec.bonus_amount = 0.0

