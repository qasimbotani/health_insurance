from odoo import models, fields, api
from odoo.exceptions import ValidationError


class InsuranceReinsuranceSettlement(models.Model):
    _name = 'insurance.reinsurance.settlement'
    _description = 'Reinsurance Settlement'
    _order = 'period_start desc'

    # -----------------------------
    # CORE IDENTIFIERS
    # -----------------------------
    name = fields.Char(
        string='Settlement Reference',
        required=True,
        readonly=True,
        copy=False,
        default='New',
        index=True,
    )

    reinsurance_contract_id = fields.Many2one(
        'insurance.reinsurance.contract',
        string='Reinsurance Contract',
        required=True,
    )

    period_start = fields.Date(
        string='Period Start',
        required=True,
    )

    period_end = fields.Date(
        string='Period End',
        required=True,
    )

    # -----------------------------
    # FINANCIALS
    # -----------------------------
    total_ceded_amount = fields.Float(
        string='Total Ceded Amount',
        readonly=True,
    )

    # -----------------------------
    # RELATIONS
    # -----------------------------
    bordereau_ids = fields.One2many(
        'insurance.reinsurance.bordereau',
        'settlement_id',
        string='Bordereaux',
        readonly=True,
    )

    # -----------------------------
    # STATE
    # -----------------------------
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('settled', 'Settled'),
        ],
        default='draft',
        tracking=True,
    )

    # -----------------------------
    # SEQUENCE
    # -----------------------------
    @api.model
    def create(self, vals_list):
        # Odoo may pass a single dict OR a list of dicts
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'insurance.reinsurance.settlement'
                ) or 'New'

        return super().create(vals_list)


    # -----------------------------
    # ACTIONS
    # -----------------------------
    def action_confirm(self):
        for rec in self:
            if not rec.bordereau_ids:
                raise ValidationError("Cannot confirm a settlement without bordereaux.")
            rec.state = 'confirmed'

    def action_settle(self):
        for rec in self:
            if rec.state != 'confirmed':
                raise ValidationError("Settlement must be confirmed first.")
            rec.state = 'settled'
