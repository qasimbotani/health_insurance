from odoo import models, fields

class ResCompany(models.Model):
    _inherit = 'res.company'

    insurance_payment_journal_id = fields.Many2one(
        'account.journal',
        string='Insurance Payment Journal',
        domain="[('type', 'in', ('bank', 'cash'))]",
        help='Journal used to pay insurance claims',
    )
    insurance_claim_expense_account_id = fields.Many2one(
            'account.account',
            string='Default Insurance Claim Expense Account',
            domain=[('account_type', '=', 'expense')],
        )