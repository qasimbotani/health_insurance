from odoo import models, fields

class InsuranceClaimVote(models.Model):
    _name = 'insurance.claim.vote'
    _description = 'Medical Committee Vote'
    _order = 'create_date asc'

    claim_id = fields.Many2one(
        'insurance.claim',
        required=True,
        ondelete='cascade',
    )

    user_id = fields.Many2one(
        'res.users',
        required=True,
        default=lambda self: self.env.user,
        ondelete='cascade',
    )

    decision = fields.Selection(
        [
            ('approve', 'Approve'),
            ('reject', 'Reject'),
        ],
        required=True,
    )

    note = fields.Text()

    _sql_constraints = [
        (
            'uniq_vote_per_user_per_claim',
            'unique(claim_id, user_id)',
            'You have already voted on this claim.'
        )
    ]
