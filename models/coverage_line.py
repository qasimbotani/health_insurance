from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError

class InsuranceCoverageLine(models.Model):
    _name = 'insurance.coverage.line'
    _description = 'Coverage Line'

    template_id = fields.Many2one(
        'insurance.coverage.template',
        required=True,
        ondelete='cascade',
    )

    service_id = fields.Many2one(
        'insurance.service',
        string='Service',
        required=True,
        ondelete='restrict',
    )

    covered = fields.Boolean(default=True)

    annual_limit = fields.Float(string='Annual Limit')

    per_claim_limit = fields.Float(string='Per Claim Limit')

    copay_percentage = fields.Float(string='Copay %')

    used_amount = fields.Float(
        string='Used Amount',
        default=0.0,
    )

    remaining_amount = fields.Float(
        compute='_compute_remaining',
        store=True,
    )
    last_reset_year = fields.Integer(
        string='Last Reset Year',
        default=lambda self: fields.Date.today().year,
    )

    utilization_percent = fields.Float(
        compute='_compute_utilization',
        store=True,
    )
    def reset_annual_usage(self):
        current_year = fields.Date.today().year

        for rec in self:
            if rec.last_reset_year != current_year:
                rec.used_amount = 0.0
                rec.last_reset_year = current_year

    @api.depends('annual_limit', 'used_amount')
    def _compute_remaining(self):
        for rec in self:
            rec.remaining_amount = max(
                (rec.annual_limit or 0.0) - rec.used_amount, 0.0
            )

    @api.depends('annual_limit', 'used_amount')
    def _compute_utilization(self):
        for rec in self:
            if rec.annual_limit:
                rec.utilization_percent = (rec.used_amount / rec.annual_limit) * 100
            else:
                rec.utilization_percent = 0.0
    @api.constrains('used_amount', 'annual_limit')
    def _check_usage_not_exceed_limit(self):
        for rec in self:
            if rec.annual_limit and rec.used_amount > rec.annual_limit:
                raise ValidationError(
                    "Coverage usage cannot exceed annual limit."
                )
    def cron_reset_coverage_usage(self):
        lines = self.search([])
        lines.reset_annual_usage()
