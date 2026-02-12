from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class InsurancePolicyDocumentRequirement(models.Model):
    _name = "insurance.policy.document.requirement"

    policy_id = fields.Many2one("insurance.policy", required=True)
    document_type = fields.Selection(
        [
            ("id_card", "ID Card"),
            ("passport", "Passport"),
            ("medical_report", "Medical Report"),
            ("company_letter", "Company Letter"),
        ]
    )
    mandatory = fields.Boolean(default=True)
