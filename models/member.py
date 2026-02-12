from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import timedelta


class InsuranceMember(models.Model):
    _name = "insurance.member"
    _description = "Insured Member"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    # -------------------------------------------------
    # BASIC INFO
    # -------------------------------------------------

    name = fields.Char(required=True, tracking=True)

    member_number = fields.Char(
        string="Member Number",
        readonly=True,
        copy=False,
        tracking=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("pending_documents", "Pending Documents"),
            ("approved", "Approved"),
            ("active", "Active"),
            ("suspended", "Suspended"),
            ("terminated", "Terminated"),
        ],
        default="draft",
        tracking=True,
    )

    company_id = fields.Many2one(
        "res.company",
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
    )

    policy_id = fields.Many2one(
        "insurance.policy",
        required=True,
        tracking=True,
    )

    partner_id = fields.Many2one(
        "res.partner",
        string="Accounting Partner",
        required=True,
    )

    # -------------------------------------------------
    # 📊 RISK ENGINE
    # -------------------------------------------------

    risk_score = fields.Float(
        compute="_compute_risk_score",
        store=True,
        tracking=True,
    )

    risk_level = fields.Selection(
        [
            ("low", "Low"),
            ("medium", "Medium"),
            ("high", "High"),
        ],
        compute="_compute_risk_score",
        store=True,
        tracking=True,
    )

    requires_underwriter = fields.Boolean(
        compute="_compute_risk_score",
        store=True,
        tracking=True,
    )

    @api.depends("claim_ids.approved_amount", "policy_id.risk_threshold")
    def _compute_risk_score(self):
        for rec in self:

            # Basic scoring logic (extendable)
            score = 0

            # Claim history factor
            total_claimed = sum(
                rec.claim_ids.filtered(lambda c: c.state == "approved").mapped(
                    "approved_amount"
                )
            )

            if rec.policy_id and rec.policy_id.annual_limit:
                utilization_ratio = total_claimed / rec.policy_id.annual_limit
                score += utilization_ratio * 100

            rec.risk_score = round(score, 2)

            # Risk level classification
            if score < 30:
                rec.risk_level = "low"
            elif score < 70:
                rec.risk_level = "medium"
            else:
                rec.risk_level = "high"

            # Underwriter requirement logic
            policy = rec.policy_id
            if not policy:
                rec.requires_underwriter = False
                continue

            if policy.auto_underwriter_required:
                rec.requires_underwriter = True
            elif score >= policy.risk_threshold:
                rec.requires_underwriter = True
            else:
                rec.requires_underwriter = False

    # -------------------------------------------------
    # 💰 PREMIUM / PAYMENT TRACKING
    # -------------------------------------------------

    premium_invoice_id = fields.Many2one(
        "account.move",
        string="Premium Invoice",
        readonly=True,
        copy=False,
    )

    premium_due_date = fields.Date(readonly=True)

    payment_status = fields.Selection(
        [
            ("not_invoiced", "Not Invoiced"),
            ("invoiced", "Invoiced"),
            ("paid", "Paid"),
            ("overdue", "Overdue"),
        ],
        compute="_compute_payment_status",
        store=True,
        tracking=True,
    )

    @api.depends("premium_invoice_id.payment_state", "premium_due_date")
    def _compute_payment_status(self):
        today = fields.Date.today()

        for rec in self:

            if not rec.premium_invoice_id:
                rec.payment_status = "not_invoiced"
                continue

            invoice = rec.premium_invoice_id

            if invoice.payment_state == "paid":
                rec.payment_status = "paid"
                continue

            if rec.premium_due_date and today > rec.premium_due_date:
                rec.payment_status = "overdue"
            else:
                rec.payment_status = "invoiced"

    # -------------------------------------------------
    # CLAIMS
    # -------------------------------------------------

    claim_ids = fields.One2many(
        "insurance.claim",
        "member_id",
    )

    total_claimed = fields.Float(
        compute="_compute_total_claimed",
        store=True,
    )

    remaining_annual_limit = fields.Float(
        compute="_compute_remaining_limit",
        store=True,
    )

    utilization_percent = fields.Float(
        compute="_compute_utilization_percent",
        store=True,
    )

    @api.depends("claim_ids.state", "claim_ids.approved_amount")
    def _compute_total_claimed(self):
        for rec in self:
            approved = rec.claim_ids.filtered(lambda c: c.state == "approved")
            rec.total_claimed = sum(approved.mapped("approved_amount"))

    @api.depends("total_claimed", "policy_id.annual_limit")
    def _compute_remaining_limit(self):
        for rec in self:
            if rec.policy_id:
                rec.remaining_annual_limit = max(
                    rec.policy_id.annual_limit - rec.total_claimed,
                    0.0,
                )
            else:
                rec.remaining_annual_limit = 0.0

    @api.depends("total_claimed", "policy_id.annual_limit")
    def _compute_utilization_percent(self):
        for rec in self:
            if rec.policy_id and rec.policy_id.annual_limit:
                rec.utilization_percent = (
                    rec.total_claimed / rec.policy_id.annual_limit
                ) * 100
            else:
                rec.utilization_percent = 0.0

    # -------------------------------------------------
    # 📝 UNDERWRITING DOCUMENTS
    # -------------------------------------------------

    document_ids = fields.One2many(
        "insurance.member.document",
        "member_id",
        string="Underwriting Documents",
    )

    underwriting_complete = fields.Boolean(
        compute="_compute_underwriting_complete",
        store=True,
    )

    @api.depends("document_ids.document_type", "document_ids.verified")
    def _compute_underwriting_complete(self):
        required_types = ["id", "application", "medical"]

        for rec in self:
            uploaded_types = rec.document_ids.filtered(lambda d: d.verified).mapped(
                "document_type"
            )

            rec.underwriting_complete = all(
                doc in uploaded_types for doc in required_types
            )

    # -------------------------------------------------
    # ONBOARDING WORKFLOW
    # -------------------------------------------------

    def action_submit_for_review(self):
        for rec in self:
            if rec.state != "draft":
                continue

            if rec.policy_id.state != "active":
                raise ValidationError("Policy must be active.")

            rec.state = "pending_documents"
            rec.message_post(body="📄 Submitted for underwriting review.")

    def action_approve(self):
        for rec in self:

            if rec.state != "pending_documents":
                raise ValidationError("Member must be pending review.")

            if not rec.underwriting_complete:
                raise ValidationError("All required documents must be verified.")

            if rec.requires_underwriter and not self.env.user.has_group(
                "insurance_core.group_underwriter"
            ):
                raise ValidationError("Underwriter approval required.")

            rec.state = "approved"
            rec.message_post(body="✅ Member approved.")

    def action_activate(self):
        for rec in self:

            if rec.state != "approved":
                raise ValidationError("Member must be approved first.")

            if rec.policy_id.state != "active":
                raise ValidationError("Policy must be active.")

            rec.member_number = (
                self.env["ir.sequence"].next_by_code("insurance.member") or "MEM-NEW"
            )

            rec.state = "active"
            rec.message_post(body=f"🎉 Activated. Member Number: {rec.member_number}")

            rec._create_premium_invoice()

    def action_suspend(self):
        for rec in self:
            if rec.state != "active":
                raise ValidationError("Only active members can be suspended.")
            rec.state = "suspended"
            rec.message_post(body="⚠️ Suspended.")

    def action_terminate(self):
        for rec in self:
            rec.state = "terminated"
            rec.message_post(body="⛔ Terminated.")

    # -------------------------------------------------
    # PREMIUM INVOICE CREATION
    # -------------------------------------------------

    def _create_premium_invoice(self):
        self.ensure_one()

        policy = self.policy_id
        company = policy.company_id

        if not policy.premium_amount:
            raise ValidationError("Policy premium amount not configured.")

        if not policy.premium_income_account_id:
            raise ValidationError("Premium income account not configured.")

        journal = self.env["account.journal"].search(
            [("type", "=", "sale"), ("company_id", "=", company.id)],
            limit=1,
        )

        if not journal:
            raise ValidationError("No Sales Journal found for company.")

        invoice = self.env["account.move"].create(
            {
                "move_type": "out_invoice",
                "partner_id": self.partner_id.id,
                "company_id": company.id,
                "invoice_date": fields.Date.today(),
                "journal_id": journal.id,
                "ref": f"Premium - {policy.name} - {self.name}",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Insurance Premium - {policy.name}",
                            "quantity": 1,
                            "price_unit": policy.premium_amount,
                            "account_id": policy.premium_income_account_id.id,
                        },
                    )
                ],
            }
        )

        invoice.action_post()

        self.premium_invoice_id = invoice.id
        self.premium_due_date = fields.Date.today() + timedelta(
            days=policy.premium_grace_days
        )

        self.message_post(body=f"💰 Premium invoice created: {invoice.name}")

    # -------------------------------------------------
    # AUTO-SUSPEND CRON
    # -------------------------------------------------

    @api.model
    def cron_auto_suspend_unpaid_members(self):
        members = self.search(
            [("state", "=", "active"), ("payment_status", "=", "overdue")]
        )

        for member in members:
            member.state = "suspended"
            member.message_post(body="⛔ Auto-suspended due to unpaid premium.")

    # -------------------------------------------------
    # ACTION
    # -------------------------------------------------

    def action_open_invoice(self):
        self.ensure_one()

        if not self.premium_invoice_id:
            return

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "view_mode": "form",
            "res_id": self.premium_invoice_id.id,
        }
