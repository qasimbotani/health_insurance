from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ReinsuranceBordereauLine(models.Model):
    _name = 'insurance.reinsurance.bordereau.line'
    _description = 'Reinsurance Bordereau Line'
    _order = 'loss_date'

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

    # ------------------------
    # SNAPSHOT FIELDS
    # ------------------------
    loss_date = fields.Date(
        string='Loss Date',
        compute='_compute_loss_date',
        store=True
    )


    member_id = fields.Many2one(
        related='claim_id.member_id',
        store=True
    )

    provider_id = fields.Many2one(
        related='claim_id.provider_id',
        store=True
    )

    service_id = fields.Many2one(
        related='claim_id.service_id',
        store=True
    )

    claimed_amount = fields.Float(
        related='claim_id.claimed_amount',
        store=True
    )

    approved_amount = fields.Float(
        related='claim_id.approved_amount',
        store=True
    )

    reinsurer_share = fields.Float(
        related='claim_id.reinsurer_share',
        store=True
    )
    @api.depends('claim_id.approved_date')
    def _compute_loss_date(self):
        for rec in self:
            if rec.claim_id.approved_date:
                rec.loss_date = rec.claim_id.approved_date.date()
            else:
                rec.loss_date = False
