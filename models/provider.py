from odoo import models, fields, api
from odoo.exceptions import ValidationError


class InsuranceProvider(models.Model):
    _name = "insurance.provider"
    _description = "Medical Provider"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)

    total_paid = fields.Float(compute="_compute_total_paid", store=True)
    partner_id = fields.Many2one(
        "res.partner",
        string="Accounting Partner",
        required=True,
        help="Partner used for payments and accounting",
    )
    expense_account_id = fields.Many2one(
        "account.account",
        string="Expense Account",
        required=True,
        domain="[('account_type', '=', 'expense'), ('company_ids', 'in', company_id)]",
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
        index=True,
    )

    @api.depends()
    def _compute_total_paid(self):
        for rec in self:
            claims = self.env["insurance.claim"].search(
                [("provider_id", "=", rec.id), ("state", "=", "approved")]
            )
            rec.total_paid = sum(claims.mapped("approved_amount"))

    @api.constrains("expense_account_id")
    def _check_expense_account_company(self):
        for rec in self:
            if not rec.expense_account_id:
                continue

            # Get company from context (claim / policy driven)
            company = self.env.company

            if company not in rec.expense_account_id.company_ids:
                raise ValidationError(
                    "The selected expense account is not allowed for the current company."
                )

    @api.constrains("partner_id")
    def _ensure_partner_payable_account(self):
        for rec in self:
            partner = rec.partner_id
            if not partner:
                continue

            if not partner.property_account_payable_id:
                default_payable = rec.company_id.account_default_payable_account_id
                if not default_payable:
                    raise ValidationError(
                        "No default payable account is configured for the company."
                    )

                partner.property_account_payable_id = default_payable
