from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import date, timedelta


class InsurancePolicy(models.Model):
    _name = "insurance.policy"
    _description = "Insurance Policy"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "start_date desc"

    # -------------------------------------------------
    # BASIC INFO
    # -------------------------------------------------

    name = fields.Char(
        string="Policy",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        index=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Insurance Company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    # One Policy → Many Members
    member_ids = fields.One2many(
        "insurance.member",
        "policy_id",
        string="Covered Members",
    )

    member_count = fields.Integer(
        compute="_compute_member_count",
        string="Members",
    )

    # -------------------------------------------------
    # PREMIUM CONFIGURATION
    # -------------------------------------------------

    premium_amount = fields.Monetary(
        string="Annual Premium",
        required=True,
        tracking=True,
        currency_field="currency_id",
    )

    currency_id = fields.Many2one(
        "res.currency",
        related="company_id.currency_id",
        readonly=True,
        store=True,
    )

    premium_income_account_id = fields.Many2one(
        "account.account",
        string="Premium Income Account",
        domain="[('account_type','=','income')]",
        help="Revenue account for insurance premiums",
    )

    premium_grace_days = fields.Integer(
        string="Premium Grace Period (Days)",
        default=15,
    )

    # -------------------------------------------------
    # UNDERWRITING RISK CONFIGURATION
    # -------------------------------------------------

    risk_evaluation_mode = fields.Selection(
        [
            ("none", "No Risk Evaluation"),
            ("member", "Member Risk Only"),
            ("policy", "Policy Risk Only"),
            ("both", "Member + Policy"),
        ],
        string="Risk Evaluation Mode",
        default="member",
        tracking=True,
    )

    risk_threshold = fields.Float(
        string="Risk Threshold",
        default=50,
        help="If member risk score exceeds this value, underwriter approval is required.",
    )

    auto_underwriter_required = fields.Boolean(
        string="Force Underwriter Approval",
        help="If enabled, all members require underwriter approval regardless of risk score.",
    )

    # -------------------------------------------------
    # POLICY PERIOD
    # -------------------------------------------------

    start_date = fields.Date(required=True, tracking=True)
    end_date = fields.Date(required=True, tracking=True)

    # -------------------------------------------------
    # STATE MACHINE
    # -------------------------------------------------

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("active", "Active"),
            ("expiring", "Expiring Soon"),
            ("renewal_quoted", "Renewal Quoted"),
            ("renewed", "Renewed"),
            ("expired", "Expired"),
            ("cancelled", "Cancelled"),
        ],
        default="draft",
        tracking=True,
    )

    # -------------------------------------------------
    # LIMITS
    # -------------------------------------------------

    annual_limit = fields.Float(required=True, tracking=True)
    manager_approval_limit = fields.Float(required=True, tracking=True)

    # -------------------------------------------------
    # COVERAGE TEMPLATE
    # -------------------------------------------------

    coverage_template_id = fields.Many2one(
        "insurance.coverage.template",
        string="Coverage Template",
        required=True,
    )

    coverage_line_ids = fields.One2many(
        "insurance.coverage.line",
        related="coverage_template_id.line_ids",
        readonly=True,
    )

    # -------------------------------------------------
    # COMPUTES
    # -------------------------------------------------

    def _compute_member_count(self):
        for rec in self:
            rec.member_count = len(rec.member_ids)

    # -------------------------------------------------
    # ACTIONS
    # -------------------------------------------------

    def action_activate(self):
        for rec in self:
            if rec.state != "draft":
                raise ValidationError("Only draft policies can be activated.")

            if rec.start_date > rec.end_date:
                raise ValidationError("End date must be after start date.")

            rec.state = "active"
            rec.message_post(body="✅ Policy activated.")

    def action_cancel(self):
        for rec in self:
            rec.state = "cancelled"
            rec.message_post(body="❌ Policy cancelled.")

    # -------------------------------------------------
    # RENEWAL
    # -------------------------------------------------

    renewal_origin_id = fields.Many2one(
        "insurance.policy",
        string="Renewed From",
        readonly=True,
        copy=False,
    )

    renewal_child_id = fields.Many2one(
        "insurance.policy",
        string="Renewal Policy",
        readonly=True,
        copy=False,
    )

    def action_generate_renewal_quote(self):
        for rec in self:
            if rec.state != "expiring":
                raise ValidationError(
                    "Renewal quotes can only be generated for expiring policies."
                )

            rec.state = "renewal_quoted"
            rec.message_post(body="📄 Renewal quote generated.")

    def action_confirm_renewal(self):
        for rec in self:
            if rec.state != "renewal_quoted":
                raise ValidationError("Only renewal-quoted policies can be renewed.")

            new_policy = rec.copy(
                {
                    "name": "New",
                    "state": "draft",
                    "start_date": rec.end_date + timedelta(days=1),
                    "end_date": rec.end_date + timedelta(days=365),
                    "renewal_origin_id": rec.id,
                }
            )

            rec.renewal_child_id = new_policy.id
            rec.state = "renewed"

            rec.message_post(
                body=f"🔁 Policy renewed. New Policy Created: {new_policy.name}"
            )

            new_policy.message_post(body=f"🔁 Renewal created from Policy {rec.name}")

    # -------------------------------------------------
    # SMART BUTTON ACTION
    # -------------------------------------------------

    def action_view_members(self):
        self.ensure_one()

        return {
            "type": "ir.actions.act_window",
            "name": "Policy Members",
            "res_model": "insurance.member",
            "view_mode": "list,form",
            "domain": [("policy_id", "=", self.id)],
            "context": {"default_policy_id": self.id},
        }

    # -------------------------------------------------
    # CRON
    # -------------------------------------------------

    @api.model
    def cron_update_policy_states(self):
        today = date.today()
        policies = self.search([("state", "in", ["active", "expiring"])])

        for policy in policies:

            if policy.end_date and policy.end_date < today:
                policy.state = "expired"
                policy.message_post(body="⛔ Policy expired automatically.")
                continue

            days_left = (policy.end_date - today).days if policy.end_date else 0

            if policy.state == "active" and days_left <= 90:
                policy.state = "expiring"
                policy.message_post(
                    body=f"⚠️ Policy entering expiry window. {days_left} days left."
                )

    # -------------------------------------------------
    # SEQUENCE
    # -------------------------------------------------

    @api.model
    def create(self, vals_list):
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("insurance.policy") or "New"
                )

        return super().create(vals_list)
