from odoo import models, fields, api
from odoo.exceptions import ValidationError

class InsuranceCoverageTemplate(models.Model):
    _name = 'insurance.coverage.template'
    _description = 'Insurance Coverage Template'

    name = fields.Char(
        string='Template Name',
        required=True
    )

    active = fields.Boolean(default=True)

    description = fields.Text()

    line_ids = fields.One2many(
        'insurance.coverage.line',
        'template_id',
        string='Covered Items'
    )
