from odoo import models, fields, api


class InsuranceMember(models.Model):
    _name = 'insurance.member'
    _description = 'Insured Member'

    name = fields.Char(required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company'
    )

    policy_id = fields.Many2one(
        'insurance.policy',
        required=True
    )

    total_claimed = fields.Float(
        compute='_compute_total_claimed',
        store=True
    )
    claim_ids = fields.One2many(
        'insurance.claim',
        'member_id',
        string='Claims',
    )
    def action_print_welcome_pack(self):
        self.ensure_one()
        return self.env.ref('insurance_core.action_member_welcome_pack').report_action(self)


    def action_print_id_card(self):
        self.ensure_one()
        return self.env.ref('insurance_core.action_member_id_card').report_action(self)

    # (Optional but VERY professional) Auto-send email on activation
    # def action_activate(self):
    #     self.state = 'active'

    #     template = self.env.ref(
    #         'insurance_core.email_template_member_welcome'
    #     )
    #     template.send_mail(self.id, force_send=True)

    remaining_annual_limit = fields.Float(
    compute='_compute_remaining_limit',
    store=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Accounting Partner',
        required=True,
        help='Partner used for reimbursements'
    )

    utilization_percent = fields.Float(
        compute='_compute_utilization_percent',
        store=True
    )
    @api.depends('total_claimed', 'policy_id.annual_limit')
    def _compute_remaining_limit(self):
        for rec in self:
            if rec.policy_id:
                rec.remaining_annual_limit = max(
                    rec.policy_id.annual_limit - rec.total_claimed,
                    0.0
                )
            else:
                rec.remaining_annual_limit = 0.0


    @api.depends('total_claimed', 'policy_id.annual_limit')
    def _compute_utilization_percent(self):
        for rec in self:
            if rec.policy_id and rec.policy_id.annual_limit:
                rec.utilization_percent = (
                    rec.total_claimed / rec.policy_id.annual_limit
                ) * 100
            else:
                rec.utilization_percent = 0.0


    @api.depends(
        'claim_ids.state',
        'claim_ids.approved_amount',
    )
    def _compute_total_claimed(self):
        for rec in self:
            claims = self.env['insurance.claim'].search([
                ('member_id', '=', rec.id),
                ('state', '=', 'approved')
            ])
            rec.total_claimed = sum(claims.mapped('approved_amount'))
    @api.onchange('company_id')
    def _onchange_company_id(self):
        if self.company_id:
            policy = self.env['insurance.policy'].search([
                ('company_id', '=', self.company_id.id),
                ('state', '=', 'active'),
            ], limit=1)

            self.policy_id = policy
