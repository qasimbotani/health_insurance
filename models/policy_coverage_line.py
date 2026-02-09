from odoo import models, fields, api


class InsurancePolicyCoverageLine(models.Model):
    _name = 'insurance.policy.coverage.line'
    _description = 'Policy Coverage Line'
    _order = 'service_id'

    policy_id = fields.Many2one(
        'insurance.policy',
        required=True,
        ondelete='cascade'
    )

    service_id = fields.Many2one(
        'insurance.service',
        required=True
    )

    covered = fields.Boolean(default=True)

    annual_limit = fields.Float()
    per_claim_limit = fields.Float()
    copay_percentage = fields.Float()
