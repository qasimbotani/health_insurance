from odoo import models, fields


class InsuranceService(models.Model):
    _name = 'insurance.service'
    _description = 'Insurance Service'
    _order = 'name'

    name = fields.Char(
        string='Service Name',
        required=True,
    )

    code = fields.Char(
        string='Service Code',
        required=True,
        help='Short internal code (e.g. LAB, RAD, SURG)'
    )

    active = fields.Boolean(
        default=True
    )

    description = fields.Text(
        string='Description'
    )

    _sql_constraints = [
        ('service_code_unique', 'unique(code)', 'Service code must be unique.')
    ]
