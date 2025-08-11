from odoo import models, fields, api
from odoo.exceptions import UserError


class NBeautyPrepaidCardTransaction(models.Model):
    _name = 'nbeauty.prepaid.card.transaction'
    _description = 'Prepaid Card Transaction Log'
    _order = 'date desc'

    card_id = fields.Many2one('nbeauty.prepaid.card', string='Card', required=True, ondelete='cascade')
    customer_id = fields.Many2one('res.partner', string='Customer', related='card_id.customer_id', store=True)

    transaction_type = fields.Selection([
        ('topup', 'Top-Up'),
        ('pos_payment', 'POS Payment'),
        ('bonus', 'Bonus Credit'),
        ('adjustment', 'Manual Adjustment'),
        ('issuance', 'Card Issuance'),
        ('refund', 'Refund'),
    ], required=True, string="Transaction Type")

    description = fields.Char(string="Description")
    amount = fields.Monetary(string="Amount", required=True)
    balance_after = fields.Monetary(string="Balance After", required=True)

    currency_id = fields.Many2one('res.currency', string="Currency", related='card_id.currency_id', store=True)
    pos_order_id = fields.Many2one('pos.order', string="POS Order", readonly=True)
    user_id = fields.Many2one('res.users', string="Handled By", default=lambda self: self.env.user, readonly=True)
    date = fields.Datetime(string="Transaction Date", default=fields.Datetime.now, readonly=True)
    branch_id = fields.Many2one('stock.warehouse', string="Branch")
    state = fields.Selection([
        ('confirmed', 'Confirmed'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default="confirmed", tracking=True)

    @api.model
    def create_topup_transaction(self, card_id, amount, description='', branch_id=None):
        card = self.env['nbeauty.prepaid.card'].browse(card_id)
        balance_after = card.balance + amount
        card.write({'balance': balance_after})
        return self.create({
            'card_id': card.id,
            'amount': amount,
            'transaction_type': 'topup',
            'balance_after': balance_after,
            'description': description or 'Top-Up',
            'branch_id': branch_id,
        })

    @api.model
    def create(self, vals):
        record = super().create(vals)
        if record.transaction_type == 'topup':
            record._create_accounting_entry_topup()
        elif record.transaction_type == 'pos_payment':
            record._create_accounting_entry_payment()
        elif record.transaction_type == 'bonus':
            record._create_accounting_entry_bonus()
        elif record.transaction_type == 'adjustment':
            record._create_accounting_entry_adjustment()
        elif record.transaction_type == 'issuance':
            record._create_accounting_entry_issuance()
        elif record.transaction_type == 'refund':
            record._create_accounting_entry_refund()
        return record

    def _get_account(self, code, name, account_type, reconcile=False):
        account = self.env['account.account'].search([('code', '=', code)], limit=1)
        if not account:
            account = self.env['account.account'].create({
                'name': name,
                'code': code,
                'account_type': account_type,
                'reconcile': reconcile,
            })
        return account

    def _create_accounting_entry_topup(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'date': fields.Date.today(),
            'ref': f"N Card Top-Up - {self.card_id.name}",
            'line_ids': [
                (0, 0, {
                    'account_id': journal.default_account_id.id,
                    'partner_id': self.customer_id.id,
                    'name': 'N Card Top-Up',
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': liability_account.id,
                    'partner_id': self.customer_id.id,
                    'name': 'N Card Top-Up Liability',
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ]
        })
        move.action_post()

    def _create_accounting_entry_payment(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('code', '=', 'NCARD')], limit=1)
        if not journal:
            raise UserError("The journal with code 'NCARD' is missing. Please create it in Accounting > Configuration > Journals.")
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        sales_account = self._get_account('NCARDSALES', 'N Card Sales', 'income')
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'move_type': 'entry',
            'date': fields.Date.today(),
            'ref': f"N Card POS Payment - {self.card_id.name}",
            'line_ids': [
                (0, 0, {
                    'account_id': liability_account.id,
                    'partner_id': self.customer_id.id,
                    'name': 'N Card POS Payment - Liability Release',
                    'debit': self.amount,
                    'credit': 0.0,
                }),
                (0, 0, {
                    'account_id': sales_account.id,
                    'partner_id': self.customer_id.id,
                    'name': 'N Card POS Payment - Recognized Revenue',
                    'debit': 0.0,
                    'credit': self.amount,
                }),
            ]
        })
        move.action_post()

    def _create_accounting_entry_bonus(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('code', '=', 'NCARD')], limit=1)
        expense_account = self._get_account('NCARDBONUS', 'N Card Bonus Expense', 'expense')
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'ref': f"N Card Bonus - {self.card_id.name}",
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'account_id': expense_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.customer_id.id,
                }),
                (0, 0, {
                    'account_id': liability_account.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': self.customer_id.id,
                }),
            ]
        })
        move.action_post()

    def _create_accounting_entry_adjustment(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('code', '=', 'NCARD')], limit=1)
        adjustment_account = self._get_account('NCARDADJ', 'N Card Adjustment', 'equity')
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'ref': f"N Card Adjustment - {self.card_id.name}",
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'account_id': adjustment_account.id,
                    'debit': self.amount if self.amount < 0 else 0.0,
                    'credit': self.amount if self.amount > 0 else 0.0,
                    'partner_id': self.customer_id.id,
                }),
                (0, 0, {
                    'account_id': liability_account.id,
                    'debit': self.amount if self.amount > 0 else 0.0,
                    'credit': self.amount if self.amount < 0 else 0.0,
                    'partner_id': self.customer_id.id,
                }),
            ]
        })
        move.action_post()

    def _create_accounting_entry_issuance(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('type', '=', 'sale')], limit=1)
        issuance_account = self._get_account('NCARDISSUE', 'N Card Issuance Income', 'income')
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'ref': f"N Card Issuance - {self.card_id.name}",
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'account_id': issuance_account.id,
                    'credit': self.amount,
                    'debit': 0.0,
                    'partner_id': self.customer_id.id,
                }),
                (0, 0, {
                    'account_id': liability_account.id,
                    'credit': 0.0,
                    'debit': self.amount,
                    'partner_id': self.customer_id.id,
                }),
            ]
        })
        move.action_post()

    def _create_accounting_entry_refund(self):
        self.ensure_one()
        journal = self.env['account.journal'].search([('type', '=', 'cash')], limit=1)
        liability_account = self._get_account('NCARDLIAB', 'N Card Liability', 'liability_current', True)
        move = self.env['account.move'].create({
            'journal_id': journal.id,
            'ref': f"N Card Refund - {self.card_id.name}",
            'date': fields.Date.today(),
            'line_ids': [
                (0, 0, {
                    'account_id': liability_account.id,
                    'debit': self.amount,
                    'credit': 0.0,
                    'partner_id': self.customer_id.id,
                }),
                (0, 0, {
                    'account_id': journal.default_account_id.id,
                    'debit': 0.0,
                    'credit': self.amount,
                    'partner_id': self.customer_id.id,
                }),
            ]
        })
        move.action_post()

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
        card = self.env['nbeauty.prepaid.card'].search([('name', '=', card_no)], limit=1)
        if not card:
            raise UserError("Card not found.")
        if card.state != 'active':
            raise UserError("Card is not active.")
        if card.expiry_date and card.expiry_date < fields.Date.today():
            raise UserError("Card is expired.")
        if card.balance < amount:
            raise UserError("Insufficient card balance.")
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
