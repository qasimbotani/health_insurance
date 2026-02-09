from odoo import models, fields, api

class InsuranceProvider(models.Model):
    _name = 'insurance.provider'
    _description = 'Medical Provider'

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    total_paid = fields.Float(
        compute='_compute_total_paid',
        store=True
    )
    partner_id = fields.Many2one(
            'res.partner',
            string='Accounting Partner',
            required=True,
            help='Partner used for payments and accounting'
        )
    expense_account_id = fields.Many2one(
        'account.account',
        string='Expense Account',
        required=True,
        domain="[('account_type', '=', 'expense')]",
        help="Expense account used when paying this provider"
    )

    @api.depends()
    def _compute_total_paid(self):
        for rec in self:
            claims = self.env['insurance.claim'].search([
                ('provider_id', '=', rec.id),
                ('state', '=', 'approved')
            ])
            rec.total_paid = sum(claims.mapped('approved_amount'))
