from odoo import api, SUPERUSER_ID

def create_ncard_payment_method(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Check if already exists
    if env['pos.payment.method'].search([('name', '=', 'Pay with N Card')], limit=1):
        return

    # Find receivable account fallback (try to get from company)
    receivable_account = env['account.account'].search([
        ('user_type_id.name', '=', 'Receivable'),
        ('company_id', '=', env.company.id)
    ], limit=1)

    # Find cash journal
    cash_journal = env['account.journal'].search([
        ('type', '=', 'cash'),
        ('company_id', '=', env.company.id)
    ], limit=1)

    if receivable_account and cash_journal:
        env['pos.payment.method'].create({
            'name': 'Pay with N Card',
            'receivable_account_id': receivable_account.id,
            'cash_journal_id': cash_journal.id,
            'payment_method_type': 'manual',
        })
