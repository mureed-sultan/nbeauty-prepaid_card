from odoo import models, fields, api
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta, date
import random
import re



class NBeautyPrepaidCard(models.Model):
    _name = 'nbeauty.prepaid.card'
    _description = 'Issued Prepaid Card'
    _rec_name = 'name'

    name = fields.Char(required=True, readonly=True, copy=False, default='New')
    customer_id = fields.Many2one('res.partner', required=True, domain=[('customer_rank', '>', 0)])
    card_type_id = fields.Many2one('nbeauty.prepaid.card.type', required=True)
    validity_type = fields.Selection([
        ('monthly', 'Monthly'),
        ('annual', 'Annual'),
        ('custom', 'Custom'),
    ], required=True)
    issued_date = fields.Date(default=fields.Date.today)
    expiry_date = fields.Date(string="Expiry Date")
    initial_amount = fields.Float(compute="_compute_amounts", store=True)
    bonus_amount = fields.Float(compute="_compute_amounts", store=True)
    balance = fields.Float(string="Balance", store=True)
    customer_mobile = fields.Char(
        string="Customer Mobile",
        related='customer_id.mobile',
        store=True,
        readonly=True,
    )
    state = fields.Selection([
        ('active', 'Active'),
        ('expired', 'Expired'),
        ('cancelled', 'Cancelled')
    ], default="active")
    currency_id = fields.Many2one('res.currency', default=lambda self: self.env.company.currency_id.id)

    allow_expiry_edit = fields.Boolean(string='Allow Expiry Edit', compute='_compute_allow_expiry_edit', store=True)

    @api.depends('validity_type')
    def _compute_allow_expiry_edit(self):
        for rec in self:
            rec.allow_expiry_edit = rec.validity_type == 'custom'

    @api.onchange('validity_type', 'issued_date')
    def _onchange_validity_type(self):
        for rec in self:
            if rec.validity_type == 'monthly':
                rec.expiry_date = rec.issued_date + timedelta(days=30) if rec.issued_date else False
            elif rec.validity_type == 'annual':
                rec.expiry_date = rec.issued_date + timedelta(days=365) if rec.issued_date else False
            elif rec.validity_type == 'custom':
                rec.expiry_date = False

    @api.depends('card_type_id')
    def _compute_amounts(self):
        for rec in self:
            rec.initial_amount = rec.card_type_id.base_amount if rec.card_type_id else 0
            rec.bonus_amount = (rec.initial_amount * rec.card_type_id.bonus_percentage) / 100 if rec.card_type_id else 0

    @api.depends('initial_amount', 'bonus_amount')
    def _compute_balance(self):
        for rec in self:
            rec.balance = rec.initial_amount + rec.bonus_amount

    def _generate_unique_card_number(self):
        for _ in range(10):
            digits = [str(random.randint(0, 9)) for _ in range(16)]
            card_number = ''.join(digits)
            if not self.search([('name', '=', card_number)]):
                return card_number
        raise ValidationError("Unable to generate a unique card number.")

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self._generate_unique_card_number()
        return super().create(vals)

    @api.model
    def auto_expire_cards(self):
        today = date.today()
        expired_cards = self.search([
            ('expiry_date', '<', today),
            ('state', '=', 'active')
        ])
        expired_cards.write({'state': 'expired'})

    def open_topup_wizard(self):
        return {
            'name': 'Top-Up Prepaid Card',
            'type': 'ir.actions.act_window',
            'res_model': 'nbeauty.prepaid.card.topup.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_card_id': self.id,
                'default_customer_id': self.customer_id.id,
            }
        }

    import re

    @api.model
    def get_card_info(self, query, mode="card_no"):
        domain = [("state", "=", "active")]
        cleaned_query = re.sub(r"[^\d+]", "", query)  # Keep only digits and plus

        card = None

        if mode == "card_no":
            domain.append(("name", "ilike", cleaned_query))
            card = self.search(domain, limit=1)

        elif mode == "mobile":
            all_cards = self.search(domain)
            for rec in all_cards:
                mobile = rec.customer_id.mobile or ""
                cleaned_mobile = re.sub(r"[^\d+]", "", mobile)
                if cleaned_mobile.endswith(cleaned_query):  # Partial match (e.g., last 10 digits)
                    card = rec
                    break

        elif mode == "name":
            domain.append(("customer_id.name", "ilike", query))
            card = self.search(domain, limit=1)

        else:
            raise UserError("Invalid search mode.")

        if not card:
            return False

        return {
            'id': card.id,
            'card_no': card.name,
            'customer_id': [card.customer_id.id, card.customer_id.name],
            'customer_mobile': card.customer_mobile,
            'expiry_date': card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else '',
            'balance': card.balance,
            'state': card.state,
            'card_type_name': card.card_type_id.name,
        }

    def create_topup_transaction(self, card_id, amount, description, branch_id=False):
        card = self.browse(card_id)
        card.balance += amount
        self.env['nbeauty.prepaid.card.transaction'].create({
            'card_id': card.id,
            'amount': amount,
            'transaction_type': 'topup',
            'balance_after': card.balance,
            'description': description,
            'branch_id': branch_id,
        })

    @api.model
    def process_ncard_payment(self, card_no, amount, order_uid=None, pos_ref=None, branch_id=None):

        card = self.search([('name', '=', card_no)], limit=1)
        if not card:
            raise UserError("Card not found.")

        if card.state != 'active':
            raise UserError("Card is not active.")

        if card.expiry_date and card.expiry_date < fields.Date.today():
            raise UserError("Card is expired.")

        if card.balance < amount:
            raise UserError("Insufficient card balance.")

        new_balance = card.balance - amount
        card.write({'balance': new_balance})

        pos_order = self.env['pos.order'].search([('uuid', '=', order_uid)], limit=1)

        vals = {
            'card_id': card.id,
            'amount': amount,
            'transaction_type': 'pos_payment',
            'balance_after': new_balance,
            'description': f'POS Payment {pos_ref or ""}'.strip(),
            'pos_order_id': pos_order.id if pos_order else None,
        }

        if branch_id:
            vals['branch_id'] = branch_id

        self.env['nbeauty.prepaid.card.transaction'].create(vals)

        return True

    @api.model
    def search_card_popup(self, query, mode):
        domain = [("state", "=", "active")]

        if mode == "card_no":
            domain.append(("name", "ilike", query))
        elif mode == "mobile":
            domain.append(("customer_id.mobile", "ilike", query))
        elif mode == "name":
            domain.append(("customer_id.name", "ilike", query))
        else:
            return []

        return self.search_read(domain, [
            "id", "name", "balance", "expiry_date", "state",
            "customer_id", "card_type_id"
        ], limit=1)