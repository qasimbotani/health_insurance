from odoo import models, fields, api
from odoo.exceptions import ValidationError


class ReinsuranceBordereau(models.Model):
    _name = 'insurance.reinsurance.bordereau'
    _description = 'Reinsurance Bordereau'
    _order = 'period_start desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    name = fields.Char(
        required=True,
        readonly=True,
        default='New'
    )

    reinsurance_contract_id = fields.Many2one(
        'insurance.reinsurance.contract',
        required=True
    )

    period_start = fields.Date(required=True)
    period_end = fields.Date(required=True)

    line_ids = fields.One2many(
        'insurance.reinsurance.bordereau.line',
        'bordereau_id',
        string='Bordereau Lines'
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
        ],
        default='draft',
        tracking=True
    )

    total_reinsurer_share = fields.Float(
        compute='_compute_totals',
        store=True
    )
    settlement_id = fields.Many2one(
        'insurance.reinsurance.settlement',
        string='Settlement',
        ondelete='set null'
    )
    total_claims = fields.Integer(
        string='Total Claims',
        compute='_compute_totals',
        store=True
    )

    @api.depends('line_ids.reinsurer_share')
    def _compute_totals(self):
        for rec in self:
            rec.total_reinsurer_share = sum(
                rec.line_ids.mapped('reinsurer_share')
            )

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code(
                    'insurance.reinsurance.bordereau'
                ) or 'New'

        return super().create(vals_list)

    # ---------------------------
    # AUTO-GENERATE LINES
    # ---------------------------
    def action_generate_lines(self):
        for bordereau in self:
            if bordereau.state != 'draft':
                raise ValidationError("Only draft bordereaux can be generated.")

            claims = self.env['insurance.claim'].search([
                ('state', '=', 'approved'),
                ('reinsurance_contract_id', '=', bordereau.reinsurance_contract_id.id),
                ('approved_date', '>=', bordereau.period_start),
                ('approved_date', '<=', bordereau.period_end),
                ('reinsurer_share', '>', 0),
                ('bordereau_line_id', '=', False),
            ])

            for claim in claims:
                line = self.env['insurance.reinsurance.bordereau.line'].create({
                    'bordereau_id': bordereau.id,
                    'claim_id': claim.id,
                })

                # 🔒 LOCK THE CLAIM TO THIS BORDEREAU
                claim.bordereau_line_id = line.id
