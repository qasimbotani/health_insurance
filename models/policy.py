from odoo import models, fields, api
from odoo.exceptions import ValidationError


class InsurancePolicy(models.Model):
    _name = 'insurance.policy'
    _description = 'Insurance Policy'
    _order = 'start_date desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    # --------------------
    # BASIC INFO
    # --------------------

    name = fields.Char(required=True)

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        help='Corporate policy owner (if any)'
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('active', 'Active'),
            ('expired', 'Expired'),
        ],
        default='draft',
        string='Status',
        tracking=True,
    )

    start_date = fields.Date(required=True)
    end_date = fields.Date(required=True)

    annual_limit = fields.Float(
        string="Annual Coverage Limit",
        required=True
    )

    active = fields.Boolean(default=True)
    coverage_template_id = fields.Many2one(
        'insurance.coverage.template',
        string='Coverage Template',
        required=True,
        help='Defines what services are covered under this policy'
    )
    coverage_line_ids = fields.One2many(
        'insurance.policy.coverage.line',
        'policy_id',
        string='Coverage Lines'
    )
    coverage_count = fields.Integer(
        compute='_compute_coverage_count'
    )

    def _compute_coverage_count(self):
        for rec in self:
            rec.coverage_count = len(
                rec.coverage_template_id.line_ids
            ) if rec.coverage_template_id else 0


    # --------------------
    # AUTO-GENERATE LINES FROM TEMPLATE
    # --------------------
    def _generate_coverage_lines_from_template(self):
        for policy in self:
            policy.coverage_line_ids.unlink()

            template = policy.coverage_template_id
            if not template:
                continue

            lines = []
            for t_line in template.line_ids:
                lines.append((0, 0, {
                    'service_id': t_line.service_id.id,
                    'covered': t_line.covered,
                    'annual_limit': t_line.annual_limit,
                    'per_claim_limit': t_line.per_claim_limit,
                    'copay_percentage': t_line.copay_percentage,
                }))

            policy.coverage_line_ids = lines

    @api.onchange('coverage_template_id')
    def _onchange_coverage_template_id(self):
        self._generate_coverage_lines_from_template()


    # --------------------
    # APPROVAL THRESHOLDS (NEW)
    # --------------------

    manager_approval_limit = fields.Float(
        string='Manager Approval Limit',
        required=True,
        help=(
            'Claims up to this amount can be approved by a Manager. '
            'Claims above this amount require General Manager approval.'
        ),
    )

    # --------------------
    # VALIDATIONS
    # --------------------

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for rec in self:
            if rec.end_date < rec.start_date:
                raise ValidationError("End date cannot be before start date.")

    # --------------------
    # LIFECYCLE ACTIONS
    # --------------------

    def action_activate(self):
        for rec in self:
            if rec.state != 'draft':
                continue

            if not rec.coverage_line_ids:
                raise ValidationError(
                    "You must configure coverage before activating the policy."
                )

            rec.state = 'active'


    def action_expire(self):
        for rec in self:
            rec.state = 'expired'
            rec.active = False

    # --------------------
    # CRON: AUTO-EXPIRE
    # --------------------

    @api.model
    def cron_expire_policies(self):
        today = fields.Date.today()

        policies = self.search([
            ('state', '=', 'active'),
            ('end_date', '<', today),
        ])

        for policy in policies:
            policy.action_expire()
