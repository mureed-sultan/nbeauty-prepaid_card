# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError
from datetime import timedelta, date
import random
import re
import logging
import requests
import json

_logger = logging.getLogger(__name__)


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

    # amounts from type
    initial_amount = fields.Float(compute="_compute_amounts", store=True)
    bonus_amount = fields.Float(compute="_compute_amounts", store=True)

    # running balance (kept in sync by our helpers/transactions)
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
    employee_id = fields.Many2one(
        'hr.employee',
        string="Referral Employee",
        help="Assign this card to an employee (optional)."
    )

    allow_expiry_edit = fields.Boolean(string='Allow Expiry Edit', compute='_compute_allow_expiry_edit', store=True)

    _sql_constraints = [
        ('unique_customer_cardtype',
         'unique(customer_id, card_type_id)',
         'This customer already has a card of this type.')
    ]

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
            base = rec.card_type_id.base_amount if rec.card_type_id else 0.0
            percent = rec.card_type_id.bonus_percentage if rec.card_type_id else 0.0
            rec.initial_amount = base
            rec.bonus_amount = (base * (percent or 0.0)) / 100.0

    def _generate_unique_card_number(self):
        max_attempts = 20
        for _ in range(max_attempts):
            card_number = ''.join([str(random.randint(0, 9)) for _ in range(16)])
            if not self.search([('name', '=', card_number)], limit=1):
                return card_number
        raise ValidationError(_("Unable to generate a unique card number after multiple attempts. Please try again."))

    @api.model
    def create(self, vals):
        try:
            # Prevent duplicate (customer + card_type_id)
            if vals.get("customer_id") and vals.get("card_type_id"):
                existing = self.search([
                    ("customer_id", "=", vals["customer_id"]),
                    ("card_type_id", "=", vals["card_type_id"])
                ], limit=1)
                if existing:
                    raise ValidationError(
                        _("Customer '%s' already has a '%s' card.") % (existing.customer_id.name, existing.card_type_id.name)
                    )

            # Auto-generate card number if not given
            if vals.get('name', 'New') == 'New':
                vals['name'] = self._generate_unique_card_number()

            card = super().create(vals)
            card._create_issuance_transactions()

            # WhatsApp notification (best-effort)
            if card.customer_mobile:
                phone_number = (card.customer_mobile or '').replace("+", "").replace(" ", "")
                payload = json.dumps({
                    "app-key": "d6342231-fbe0-4bf2-b4b9-9475ccb202be",
                    "auth-key": "2d1e0678a72544dbaaf5fc31d2e8b9ec5015c6be085fe44b47",
                    "destination_number": phone_number,
                    "template_id": "2283941152025419",
                    "device_id": "67cfa013e9f65c8638a8fd0b",
                    "variables": [
                        card.customer_id.name,
                        card.name,
                        str(round(card.initial_amount, 2)),
                        str(round(card.bonus_amount, 2)),
                        str(round(card.balance or 0.0, 2)),
                        card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else 'No Expiry'
                    ],
                    "button_variable": [],
                    "media": "",
                    "message": ""
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

            return card

        except ValidationError:
            raise
        except Exception as e:
            _logger.error("Failed to create prepaid card: %s", str(e))
            raise UserError(_("Failed to create card. Please try again or contact support."))

    def _create_issuance_transactions(self):
        self.ensure_one()
        # initial amount
        self.env['nbeauty.prepaid.card.transaction'].create({
            'card_id': self.id,
            'amount': self.initial_amount,
            'transaction_type': 'topup',
            'balance_after': self.initial_amount,
            'description': 'Card Initial Amount'
        })
        # bonus
        if self.bonus_amount > 0:
            self.env['nbeauty.prepaid.card.transaction'].create({
                'card_id': self.id,
                'amount': self.bonus_amount,
                'transaction_type': 'bonus',
                'balance_after': self.initial_amount + self.bonus_amount,
                'description': 'Card Issuance Bonus'
            })
        self.balance = self.initial_amount + self.bonus_amount

    def write(self, vals):
        res = super().write(vals)
        if 'initial_amount' in vals or 'bonus_amount' in vals:
            self._update_balance_from_transactions()
        return res

    def _update_balance_from_transactions(self):
        for card in self:
            transactions = self.env['nbeauty.prepaid.card.transaction'].search([
                ('card_id', '=', card.id)
            ], order='create_date')
            balance = 0.0
            for trans in transactions:
                if trans.transaction_type in ('topup', 'bonus'):
                    balance += trans.amount
                elif trans.transaction_type in ('pos_payment', 'refund'):
                    balance -= trans.amount
                if trans.balance_after != balance:
                    trans.write({'balance_after': balance})
            card.balance = balance

    def action_print_card_receipt(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.report',
            'report_name': 'nbeauty_prepaid_card.report_card_receipt_template',
            'report_type': 'qweb-html',
            'model': 'nbeauty.prepaid.card',
            'docids': self.ids,
            'context': {
                'discard_logo_check': True,
                'force_report_rendering': True
            }
        }

    @api.model
    def auto_expire_cards(self):
        today = date.today()
        expired_cards = self.search([
            ('expiry_date', '<', today),
            ('state', '=', 'active')
        ])
        expired_cards.write({'state': 'expired'})

    def open_topup_wizard(self):
        """Left here in case you still open from card; but now it's a PAGE (target=current)."""
        self.ensure_one()
        return {
            'name': _('Top-Up Prepaid Card'),
            'type': 'ir.actions.act_window',
            'res_model': 'nbeauty.prepaid.card.topup.wizard',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_card_id': self.id,
                'default_customer_id': self.customer_id.id,
            }
        }

    @api.model
    def get_card_info(self, query, mode="card_no"):
        domain = [("state", "=", "active")]
        cleaned_query = re.sub(r"[^\d+]", "", query or "")
        card = None
        if mode == "card_no":
            domain.append(("name", "ilike", cleaned_query))
            card = self.search(domain, limit=1)
        elif mode == "mobile":
            all_cards = self.search(domain)
            for rec in all_cards:
                mobile = rec.customer_id.mobile or ""
                cleaned_mobile = re.sub(r"[^\d+]", "", mobile)
                if cleaned_mobile.endswith(cleaned_query):
                    card = rec
                    break
        elif mode == "name":
            domain.append(("customer_id.name", "ilike", query))
            card = self.search(domain, limit=1)
        else:
            raise UserError(_("Invalid search mode."))
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

    # ------------------------------------------------------------
    # Top-up helper (creates transaction + accounting move)
    # ------------------------------------------------------------
    def create_topup_transaction(self, card_id, amount, description="", branch_id=False, journal_id=False):
        """Create a top-up transaction for a card and (optionally) an account move."""
        card = self.browse(card_id).exists()
        if not card:
            raise UserError(_("Card not found."))

        # Update balance on the card
        new_balance = (card.balance or 0.0) + amount
        card.write({'balance': new_balance})

        # Create transaction row
        tx_vals = {
            'card_id': card.id,
            'transaction_type': 'topup',
            'amount': amount,
            'balance_after': new_balance,
            'description': description or 'Top-Up',
            'journal_id': journal_id,  # must be an int, not a record

        }
        if branch_id:
            tx_vals['branch_id'] = branch_id
        if journal_id:
            tx_vals['journal_id'] = journal_id

        tx = self.env['nbeauty.prepaid.card.transaction'].create(tx_vals)

        # ------------------------------------------------------------
        # Accounting move (Payment received → Liability)
        # ------------------------------------------------------------
        if journal_id:
            journal = self.env['account.journal'].browse(
                journal_id.id if isinstance(journal_id, models.Model) else journal_id
            )
            if not journal.exists():
                raise UserError(_("Invalid journal selected."))

            # fetch our NCard liability account
            ncard_liab = self.env.ref("your_module_name.ncard_liability_account", raise_if_not_found=False)
            if not ncard_liab:
                raise UserError(_("NCard Liability account is not configured."))

            move = self.env['account.move'].create({
                'journal_id': journal.id,
                'date': fields.Date.today(),
                'line_ids': [
                    # Debit: Payment Method (Cash/Bank/Paylink)
                    (0, 0, {
                        'account_id': journal.default_account_id.id,
                        'debit': amount,
                        'credit': 0.0,
                        'name': description or 'NCard Top-Up',
                        'partner_id': card.customer_id.id,
                    }),
                    # Credit: NCard Liability
                    (0, 0, {
                        'account_id': ncard_liab.id,
                        'debit': 0.0,
                        'credit': amount,
                        'name': description or 'NCard Top-Up',
                        'partner_id': card.customer_id.id,
                    }),
                ]
            })
            move.action_post()
            tx.account_move_id = move.id

        return tx

    @api.model
    def process_ncard_payment(self, card_no, amount, order_uid=None, pos_ref=None, branch_id=None):
        card = self.search([('name', '=', card_no)], limit=1)
        if not card:
            raise UserError(_("Card not found."))
        if card.state != 'active':
            raise UserError(_("Card is not active."))
        if card.expiry_date and card.expiry_date < fields.Date.today():
            raise UserError(_("Card is expired."))
        if (card.balance or 0.0) < amount:
            raise UserError(_("Insufficient card balance."))

        new_balance = (card.balance or 0.0) - amount
        card.write({'balance': new_balance})

        pos_order = self.env['pos.order'].search([('uuid', '=', order_uid)], limit=1)
        vals = {
            'card_id': card.id,
            'amount': amount,
            'transaction_type': 'pos_payment',
            'balance_after': new_balance,
            'description': ('POS Payment %s' % (pos_ref or '')).strip(),
            'pos_order_id': pos_order.id if pos_order else None,
        }
        if branch_id:
            vals['branch_id'] = branch_id

        self.env['nbeauty.prepaid.card.transaction'].create(vals)
        self._check_and_issue_voucher(card, amount, pos_order)
        return True

    def _check_and_issue_voucher(self, card, amount, pos_order):
        card_type = card.card_type_id
        min_spend = card_type.min_spend_for_voucher
        voucher_value = card_type.voucher_amount
        if min_spend and voucher_value and amount >= min_spend:
            self.env['nbeauty.prepaid.card.voucher'].create({
                'card_id': card.id,
                'amount': voucher_value,
                'voucher_type': 'product',
                'description': 'Auto-issued after POS payment of AED %s' % amount,
                'expiry_date': fields.Date.today() + timedelta(days=180),
                'pos_order_id': pos_order.id if pos_order else None,
            })


# ------------------------------------------------------------
# Optional helper: show phone only when context says so
# ------------------------------------------------------------
class ResPartner(models.Model):
    _inherit = 'res.partner'

    def name_get(self):
        res = []
        show_phone_only = self.env.context.get('show_phone_only')
        for partner in self:
            if show_phone_only:
                if partner.mobile:
                    res.append((partner.id, partner.mobile))
                elif partner.phone:
                    res.append((partner.id, partner.phone))
                else:
                    res.append((partner.id, 'No Phone'))
            else:
                display_name = partner.name
                if partner.mobile:
                    display_name = f"{partner.name} ({partner.mobile})"
                elif partner.phone:
                    display_name = f"{partner.name} ({partner.phone})"
                res.append((partner.id, display_name))
        return res
