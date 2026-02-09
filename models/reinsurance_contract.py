from odoo import models, fields, api
from odoo.exceptions import ValidationError


class InsuranceReinsuranceContract(models.Model):
    _name = 'insurance.reinsurance.contract'
    _description = 'Reinsurance Contract'

    name = fields.Char(
        required=True
    )

    active = fields.Boolean(
        default=True
    )

    # ----------------------------
    # SCOPE
    # ----------------------------

    policy_id = fields.Many2one(
        'insurance.policy',
        string='Policy',
        required=True,
        ondelete='cascade',
        help='Policy covered by this reinsurance contract'
    )

    reinsurer_id = fields.Many2one(
        'res.partner',
        string='Reinsurer',
        required=True,
        domain=[('is_company', '=', True)]
    )

    # ----------------------------
    # STOP-LOSS RULES
    # ----------------------------

    retention_amount = fields.Float(
        string='Retention (Company Keeps)',
        required=True,
        help='Maximum amount insurer pays per claim'
    )

    max_coverage_amount = fields.Float(
        string='Reinsurer Max Coverage',
        help='Maximum reinsurer liability per claim'
    )

    start_date = fields.Date(
        required=True
    )

    end_date = fields.Date(
        required=True
    )

    # ----------------------------
    # VALIDATIONS
    # ----------------------------

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date < rec.start_date:
                raise ValidationError("End date must be after start date.")
