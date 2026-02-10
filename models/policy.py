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
        string="Policy Number",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        index=True,
        tracking=True,
    )

    member_id = fields.Many2one(
        "insurance.member",
        string="Policy Holder",
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )

    # -------------------------------------------------
    # POLICY PERIOD
    # -------------------------------------------------

    start_date = fields.Date(
        string="Start Date",
        required=True,
        tracking=True,
    )

    end_date = fields.Date(
        string="End Date",
        required=True,
        tracking=True,
    )

    # -------------------------------------------------
    # STATE MACHINE (DIAGRAM-DRIVEN)
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
        string="Status",
        default="draft",
        tracking=True,
    )

    # -------------------------------------------------
    # LIMITS
    # -------------------------------------------------

    annual_limit = fields.Float(
        string="Annual Limit",
        required=True,
        tracking=True,
    )

    manager_approval_limit = fields.Float(
        string="Manager Approval Limit",
        required=True,
        tracking=True,
    )

    # -------------------------------------------------
    # COMPUTED FLAGS
    # -------------------------------------------------

    is_expired = fields.Boolean(
        string="Expired",
        compute="_compute_is_expired",
        store=True,
    )

    days_to_expiry = fields.Integer(
        string="Days to Expiry",
        compute="_compute_days_to_expiry",
        store=False,
    )

    # -------------------------------------------------
    # COMPUTES
    # -------------------------------------------------

    @api.depends("end_date")
    def _compute_is_expired(self):
        today = date.today()
        for rec in self:
            rec.is_expired = bool(rec.end_date and rec.end_date < today)

    @api.depends("end_date")
    def _compute_days_to_expiry(self):
        today = date.today()
        for rec in self:
            if rec.end_date:
                rec.days_to_expiry = (rec.end_date - today).days
            else:
                rec.days_to_expiry = 0

    # -------------------------------------------------
    # STATE TRANSITIONS (MANUAL)
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
            if rec.state in ("expired", "cancelled"):
                continue

            rec.state = "cancelled"

            rec.message_post(body="❌ Policy cancelled.")

    # -------------------------------------------------
    # AUTOMATIC STATE ENFORCEMENT
    # -------------------------------------------------

    def _auto_update_policy_state(self):
        """
        Enforces expiry and expiring states.
        Called by cron.
        """
        today = date.today()

        for rec in self:
            if rec.state in ("cancelled", "expired"):
                continue

            if rec.end_date < today:
                rec.state = "expired"
                rec.message_post(body="⛔ Policy expired automatically.")
                continue

            days_left = (rec.end_date - today).days

            if days_left <= 90 and rec.state == "active":
                rec.state = "expiring"
                rec.message_post(
                    body=(
                        "⚠️ Policy entering renewal window.<br/>"
                        f"Days to expiry: {days_left}"
                    )
                )

    # -------------------------------------------------
    # ORM OVERRIDES
    # -------------------------------------------------

    @api.model
    def create(self, vals):
        if vals.get("name", "New") == "New":
            vals["name"] = (
                self.env["ir.sequence"].next_by_code("insurance.policy") or "New"
            )
        return super().create(vals)

    # -------------------------------------------------
    # SMART BUTTON COUNTERS
    # -------------------------------------------------

    coverage_count = fields.Integer(
        string="Coverage Lines",
        compute="_compute_coverage_count",
        store=False,
    )

    def _compute_coverage_count(self):
        for policy in self:
            policy.coverage_count = len(policy.coverage_line_ids)

    # ----------------------------------
    # COVERAGE TEMPLATE
    # ----------------------------------

    coverage_template_id = fields.Many2one(
        "insurance.coverage.template",
        string="Coverage Template",
        required=True,
        help="Defines covered services and limits for this policy",
    )

    coverage_line_ids = fields.One2many(
        "insurance.coverage.line",
        related="coverage_template_id.line_ids",
        string="Coverage Lines",
        readonly=True,
    )
