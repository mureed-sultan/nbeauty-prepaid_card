from odoo import models, fields, api
from odoo.exceptions import UserError


class NBeautyPrepaidCardTransaction(models.Model):
    _name = 'nbeauty.prepaid.card.transaction'
    _description = 'Prepaid Card Transaction Log'
    _order = 'date desc'

    card_id = fields.Many2one(
        'nbeauty.prepaid.card',
        string='Card',
        required=True,
        ondelete='cascade'
    )
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        related='card_id.customer_id',
        store=True
    )

    transaction_type = fields.Selection([
        ('topup', 'Top-Up'),
        ('pos_payment', 'POS Payment'),
        ('bonus', 'Bonus Credit'),
        ('voucher', 'Voucher Issued'),
        ('adjustment', 'Manual Adjustment'),
        ('issuance', 'Card Issuance'),
        ('refund', 'Refund'),
    ], required=True, string="Transaction Type")

    description = fields.Char(string="Description")
    amount = fields.Monetary(string="Amount", required=True)
    balance_after = fields.Monetary(string="Balance After", required=True)

    currency_id = fields.Many2one(
        'res.currency',
        string="Currency",
        related='card_id.currency_id',
        store=True
    )
    pos_order_id = fields.Many2one(
        'pos.order',
        string="POS Order",
        readonly=True,
    )
    user_id = fields.Many2one(
        'res.users',
        string="Handled By",
        default=lambda self: self.env.user,
        readonly=True
    )
    date = fields.Datetime(string="Transaction Date", default=fields.Datetime.now, readonly=True)

    branch_id = fields.Many2one('stock.warehouse', string="Branch")

    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default="confirmed", tracking=True)

    @api.model
    def create_topup_transaction(self, card_id, amount, description=None, branch_id=None):
        """
        Creates a top-up transaction and updates the card balance.
        """
        card = self.env['nbeauty.prepaid.card'].browse(card_id)
        if not card:
            raise UserError("Card not found.")

        if card.state != 'active':
            raise UserError("Cannot top up an inactive or expired card.")

        if amount <= 0:
            raise UserError("Top-up amount must be greater than zero.")

        # Update balance
        card.balance += amount

        # Create transaction log
        return self.create({
            'card_id': card.id,
            'transaction_type': 'topup',
            'amount': amount,
            'balance_after': card.balance,
            'description': description or 'Top-Up',
            'branch_id': branch_id,
        })

    def open_pos_order(self):
        self.ensure_one()
        if not self.pos_order_id:
            raise UserError("No linked POS Order.")
        return {
            'type': 'ir.actions.act_window',
            'name': 'POS Order',
            'res_model': 'pos.order',
            'view_mode': 'form',
            'res_id': self.pos_order_id.id,
            'target': 'current',
        }


class PrepaidTransactionReport(models.TransientModel):
    _name = 'nbeauty.prepaid.transaction.report'
    _description = 'Prepaid Card Transaction Report'

    start_date = fields.Date(string="Start Date")
    end_date = fields.Date(string="End Date")
    customer_id = fields.Many2one('res.partner', string="Customer")

    transaction_ids = fields.Many2many(
        'nbeauty.prepaid.card.transaction',
        'prepaid_txn_rel',
        'report_id', 'transaction_id',
        string="Transactions"
    )

    def fetch_report(self):
        for rec in self:
            domain = []
            if rec.start_date:
                domain.append(('date', '>=', rec.start_date))
            if rec.end_date:
                domain.append(('date', '<=', rec.end_date))
            if rec.customer_id:
                domain.append(('customer_id', '=', rec.customer_id.id))

            transactions = self.env['nbeauty.prepaid.card.transaction'].search(domain)
            rec.transaction_ids = [(6, 0, transactions.ids)]

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

        # Deduct balance manually (careful since balance is compute=True in older version)
        card.write({'balance': card.balance - amount})

        pos_order = self.env['pos.order'].search([('uid', '=', order_uid)], limit=1) if order_uid else None

        self.env['nbeauty.prepaid.card.transaction'].create({
            'card_id': card.id,
            'amount': amount,
            'transaction_type': 'pos_payment',
            'balance_after': card.balance,
            'description': 'POS Payment',
            'pos_order_id': pos_order.id if pos_order else None,
            'branch_id': branch_id,
        })

        return True

