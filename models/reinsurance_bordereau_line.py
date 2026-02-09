from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ReinsuranceBordereauLine(models.Model):
    _name = 'insurance.reinsurance.bordereau.line'
    _description = 'Reinsurance Bordereau Line'
    _order = 'loss_date'

    # -------------------------------------------------
    # RELATIONSHIPS
    # -------------------------------------------------
    bordereau_id = fields.Many2one(
        'insurance.reinsurance.bordereau',
        required=True,
        ondelete='cascade'
    )

    claim_id = fields.Many2one(
        'insurance.claim',
        required=True,
        ondelete='restrict'
    )

    # -------------------------------------------------
    # SNAPSHOT FIELDS (REAL SNAPSHOT, NOT RELATED)
    # -------------------------------------------------
    loss_date = fields.Date(
        string='Loss Date',
        required=True
    )

    member_id = fields.Many2one(
        'insurance.member',
        readonly=True
    )

    provider_id = fields.Many2one(
        'insurance.provider',
        readonly=True
    )

    service_id = fields.Many2one(
        'insurance.service',
        readonly=True
    )

    claimed_amount = fields.Float(
        readonly=True
    )

    approved_amount = fields.Float(
        readonly=True
    )

    reinsurer_share = fields.Float(
        readonly=True
    )

    # -------------------------------------------------
    # CONSTRAINTS
    # -------------------------------------------------
    _sql_constraints = [
        (
            'unique_claim_per_bordereau',
            'unique(bordereau_id, claim_id)',
            'This claim already exists in this bordereau.'
        )
    ]

    # -------------------------------------------------
    # CREATE OVERRIDE → SNAPSHOT FREEZE
    # -------------------------------------------------
    @api.model
    def create(self, vals):
        claim = self.env['insurance.claim'].browse(vals.get('claim_id'))

        if not claim:
            raise ValidationError("Invalid claim.")

        if claim.state != 'approved':
            raise ValidationError("Only approved claims can be added to a bordereau.")

        if claim.payment_state != 'paid':
            raise ValidationError("Only paid claims can be added to a bordereau.")

        vals.update({
            'loss_date': claim.approved_date,
            'member_id': claim.member_id.id,
            'provider_id': claim.provider_id.id,
            'service_id': claim.service_id.id,
            'claimed_amount': claim.claimed_amount,
            'approved_amount': claim.approved_amount,
            'reinsurer_share': claim.reinsurer_share,
        })

        return super().create(vals)
