from odoo import models, fields, api
from odoo.exceptions import ValidationError, AccessError
from datetime import timedelta


class InsuranceClaim(models.Model):
    _name = "insurance.claim"
    _description = "Insurance Claim"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "create_date desc"

    # -------------------------------------------------
    # CORE RELATIONS
    # -------------------------------------------------

    member_id = fields.Many2one(
        "insurance.member",
        string="Insured Member",
        required=True,
        tracking=True,
    )

    provider_id = fields.Many2one(
        "insurance.provider",
        string="Medical Provider",
        required=True,
        tracking=True,
    )

    policy_id = fields.Many2one(
        "insurance.policy",
        string="Policy",
        related="member_id.policy_id",
        store=True,
        readonly=True,
    )

    manager_approval_limit = fields.Float(
        string="Manager Approval Limit",
        related="policy_id.manager_approval_limit",
        store=True,
        readonly=True,
    )

    service_id = fields.Many2one(
        "insurance.service",
        string="Service",
        required=True,
        tracking=True,
    )
    vote_ids = fields.One2many(
        "insurance.claim.vote",
        "claim_id",
        string="Committee Votes",
    )

    committee_quorum = fields.Integer(default=2, string="Required Approvals")

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        related="policy_id.company_id",
        store=True,
        readonly=True,
    )
    name = fields.Char(
        string="Claim Number",
        required=True,
        readonly=True,
        copy=False,
        default="New",
        index=True,
    )

    bordereau_line_id = fields.Many2one(
        "insurance.reinsurance.bordereau.line", readonly=True, copy=False
    )

    # -------------------------------------------------
    # FINANCIALS
    # -------------------------------------------------

    claimed_amount = fields.Float(
        string="Claimed Amount",
        required=True,
        tracking=True,
    )

    approved_amount = fields.Monetary(
        string="Approved Amount", currency_field="currency_id"
    )

    currency_id = fields.Many2one(
        "res.currency",
        string="Currency",
        related="company_id.currency_id",
        store=True,
        readonly=True,
    )

    payment_id = fields.Many2one(
        "account.payment",
        string="Payment",
        readonly=True,
    )

    payee_type = fields.Selection(
        [
            ("provider", "Medical Provider"),
            ("member", "Member"),
        ],
        default="provider",
        required=True,
        tracking=True,
    )

    override_used = fields.Boolean(
        string="Override Used",
        readonly=True,
        tracking=True,
    )

    override_reason = fields.Text(
        string="Override Justification",
        tracking=True,
    )

    override_by = fields.Many2one(
        "res.users",
        string="Override By",
        readonly=True,
    )

    override_date = fields.Datetime(
        string="Override Date",
        readonly=True,
    )
    sla_remaining_hours = fields.Float(
        string="SLA Remaining (Hours)",
        compute="_compute_sla_remaining",
        store=False,
    )

    sla_status = fields.Selection(
        [
            ("ok", "On Track"),
            ("warning", "Near Breach"),
            ("breached", "Breached"),
        ],
        compute="_compute_sla_remaining",
        store=False,
    )

    # -------------------------------------------------
    # WORKFLOW STATE
    # -------------------------------------------------

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted"),
            ("returned", "Returned for Correction"),
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        default="draft",
        tracking=True,
    )

    # -------------------------------------------------
    # Override Approval
    # -------------------------------------------------
    def action_override_approve(self):
        for rec in self:
            user = self.env.user

            # --------------------------------
            # ROLE CHECK
            # --------------------------------
            if not (
                user.has_group("insurance_core.group_insurance_gm")
                or user.has_group("insurance_core.group_insurance_committee")
            ):
                raise AccessError(
                    "Only General Manager or Medical Committee can override approvals."
                )

            # --------------------------------
            # STATE CHECK
            # --------------------------------
            if rec.state != "submitted":
                raise ValidationError("Only submitted claims can be override-approved.")

            # --------------------------------
            # JUSTIFICATION REQUIRED
            # --------------------------------
            if not rec.override_reason:
                raise ValidationError("Override justification is mandatory.")

            # --------------------------------
            # FRAUD SAFETY (recommended)
            # --------------------------------
            if rec.fraud_flag and not user.has_group(
                "insurance_core.group_insurance_committee"
            ):
                raise ValidationError(
                    "Fraud-flagged claims require Medical Committee override."
                )

            # --------------------------------
            # MARK OVERRIDE
            # --------------------------------
            rec.override_used = True
            rec.override_by = user
            rec.override_date = fields.Datetime.now()

            rec.message_post(
                body=(
                    "<b>⚠ OVERRIDE APPROVAL USED</b><br/>"
                    f"<b>By:</b> {user.name}<br/>"
                    f"<b>Reason:</b><br/>{rec.override_reason}"
                )
            )

            # --------------------------------
            # FINAL APPROVAL (bypass hierarchy)
            # --------------------------------
            rec.with_context(skip_hierarchy=True).action_approve()

    # -------------------------------------------------
    # Return for Amendment
    # -------------------------------------------------
    return_reason = fields.Text(string="Return Reason", tracking=True)

    def action_return_for_correction(self):
        for rec in self:
            if rec.state != "submitted":
                raise ValidationError("Only submitted claims can be returned.")

            if not self.env.user.has_group("insurance_core.group_insurance_manager"):
                raise AccessError("Only managers can return claims.")

            rec.state = "returned"

            rec.message_post(
                body="❗ Claim returned for correction. Please review manager notes and resubmit."
            )

    def action_resubmit(self):
        for rec in self:
            if rec.state != "returned":
                raise ValidationError("Only returned claims can be resubmitted.")

            rec.state = "submitted"

            rec.message_post(body="🔁 Claim corrected and resubmitted for approval.")

    # -------------------------------------------------
    # SLA COMPUTE
    # -------------------------------------------------
    @api.depends("sla_deadline", "state")
    def _compute_sla_remaining(self):
        now = fields.Datetime.now()

        for rec in self:
            if not rec.sla_deadline or rec.state != "submitted":
                rec.sla_remaining_hours = 0
                rec.sla_status = "ok"
                continue

            delta = rec.sla_deadline - now
            hours = delta.total_seconds() / 3600

            rec.sla_remaining_hours = max(hours, 0)

            if hours <= 0:
                rec.sla_status = "breached"
            elif hours <= 12:
                rec.sla_status = "warning"
            else:
                rec.sla_status = "ok"

    # -------------------------------------------------
    # FRAUD DETECTION
    # -------------------------------------------------

    fraud_score = fields.Integer(
        string="Fraud Risk Score",
        readonly=True,
        tracking=True,
        default=0,
    )

    fraud_flag = fields.Boolean(
        string="Flagged for Review",
        readonly=True,
        tracking=True,
    )

    fraud_reason = fields.Text(
        string="Fraud Notes",
        readonly=True,
    )

    # def _evaluate_fraud_risk(self):
    #     self.ensure_one()

    #     score = 0
    #     reasons = []

    #     # ---------------------------------
    #     # R1: High claim vs history
    #     # ---------------------------------
    #     avg_claim = (
    #         self.env["insurance.claim"]
    #         .search(
    #             [
    #                 ("member_id", "=", self.member_id.id),
    #                 ("state", "=", "approved"),
    #             ]
    #         )
    #         .mapped("approved_amount")
    #     )

    #     if avg_claim:
    #         avg_value = sum(avg_claim) / len(avg_claim)
    #         if self.claimed_amount > avg_value * 3:
    #             score += 30
    #             reasons.append("Claim amount unusually high vs member history.")

    #     # ---------------------------------
    #     # R2: Too many recent claims
    #     # ---------------------------------
    #     recent_claims = self.search(
    #         [
    #             ("member_id", "=", self.member_id.id),
    #             ("create_date", ">=", fields.Datetime.now() - timedelta(days=30)),
    #         ]
    #     )

    #     if len(recent_claims) >= 5:
    #         score += 20
    #         reasons.append("High number of claims in short period.")

    #     # ---------------------------------
    #     # R3: Same provider + service repetition
    #     # ---------------------------------
    #     repeated = self.search(
    #         [
    #             ("provider_id", "=", self.provider_id.id),
    #             ("service_id", "=", self.service_id.id),
    #             ("member_id", "=", self.member_id.id),
    #             ("state", "=", "approved"),
    #         ]
    #     )

    #     if len(repeated) >= 3:
    #         score += 25
    #         reasons.append("Repeated same service with same provider.")

    #     # ---------------------------------
    #     # R4: Claim shortly after policy start
    #     # ---------------------------------
    #     if self.policy_id:
    #         days_from_start = (fields.Date.today() - self.policy_id.start_date).days
    #         if days_from_start <= 14:
    #             score += 15
    #             reasons.append("Claim submitted shortly after policy start.")

    #     # ---------------------------------
    #     # APPLY RESULTS
    #     # ---------------------------------
    #     self.fraud_score = score
    #     self.fraud_flag = score >= 40
    #     self.fraud_reason = "\n".join(reasons)

    # -------------------------------------------------
    # FRAUD DETECTION & ESCALATION (AUTHORITATIVE)
    # -------------------------------------------------

    def _evaluate_fraud_risk(self):
        self.ensure_one()

        score = 0
        reasons = []

        # ---------------------------------
        # R1: High claim vs history
        # ---------------------------------
        avg_claims = (
            self.env["insurance.claim"]
            .search(
                [
                    ("member_id", "=", self.member_id.id),
                    ("state", "=", "approved"),
                ]
            )
            .mapped("approved_amount")
        )

        if avg_claims:
            avg_value = sum(avg_claims) / len(avg_claims)
            if self.claimed_amount > avg_value * 3:
                score += 30
                reasons.append("Claim amount unusually high vs member history.")

        # ---------------------------------
        # R2: Too many recent claims
        # ---------------------------------
        recent_claims = self.search(
            [
                ("member_id", "=", self.member_id.id),
                ("create_date", ">=", fields.Datetime.now() - timedelta(days=30)),
            ]
        )

        if len(recent_claims) >= 5:
            score += 20
            reasons.append("High number of claims in short period.")

        # ---------------------------------
        # R3: Same provider + service repetition
        # ---------------------------------
        repeated = self.search(
            [
                ("provider_id", "=", self.provider_id.id),
                ("service_id", "=", self.service_id.id),
                ("member_id", "=", self.member_id.id),
                ("state", "=", "approved"),
            ]
        )

        if len(repeated) >= 3:
            score += 25
            reasons.append("Repeated same service with same provider.")

        # ---------------------------------
        # R4: Claim shortly after policy start
        # ---------------------------------
        if self.policy_id:
            days_from_start = (fields.Date.today() - self.policy_id.start_date).days
            if days_from_start <= 14:
                score += 15
                reasons.append("Claim submitted shortly after policy start.")

        # ---------------------------------
        # APPLY RESULTS
        # ---------------------------------
        self.fraud_score = score
        self.fraud_flag = score >= 40
        self.fraud_reason = "\n".join(reasons)

        # 🚨 AUTHORITATIVE RULE 🚨
        # Fraud ALWAYS escalates to committee
        if self.fraud_flag:
            self._force_committee_escalation()

    def _force_committee_escalation(self):
        """
        Single source of truth for committee escalation.
        """
        self.ensure_one()

        self.escalation_level = "committee"
        self.committee_required = True

        self.message_post(
            body=(
                "⚠️ <b>Fraud Risk Detected</b><br/>"
                f"Score: {self.fraud_score}<br/>"
                "Claim has been escalated to the Medical Committee."
            )
        )

    def action_flag_fraud(self):
        for rec in self:
            rec.fraud_flag = True
            rec.fraud_reason = (rec.fraud_reason or "") + "\nManually flagged."
            rec.fraud_score = max(rec.fraud_score, 50)

    # -------------------------------------------------
    # FRAUD ACTIONS
    # -------------------------------------------------

    def action_clear_fraud(self):
        if not self.env.user.has_group("insurance_core.group_insurance_manager"):
            raise AccessError("Only managers can clear fraud flags.")

        for rec in self:
            rec.fraud_flag = False
            rec.fraud_score = 0
            rec.fraud_reason = False

    # -------------------------------------------------
    # ESCALATION MATRIX
    # -------------------------------------------------

    escalation_level = fields.Selection(
        [
            ("manager", "Manager"),
            ("gm", "General Manager"),
            ("committee", "Medical Committee"),
        ],
        default="manager",
        tracking=True,
        string="Current Escalation Level",
    )

    committee_required = fields.Boolean(
        string="Medical Committee Required",
        default=False,
        tracking=True,
    )

    committee_decision = fields.Selection(
        [
            ("approved", "Approved"),
            ("rejected", "Rejected"),
        ],
        tracking=True,
    )

    committee_notes = fields.Text(
        tracking=True,
    )

    def _escalate_if_needed(self):
        for rec in self:
            # Escalate to GM
            if rec.escalation_level == "manager" and rec.approval_level == "gm":
                rec.escalation_level = "gm"

            # Escalate to Medical Committee
            if (
                rec.fraud_flag
                or rec.is_overdue
                or rec.claimed_amount > (rec.policy_id.annual_limit * 0.5)
            ):
                rec.escalation_level = "committee"
                rec.committee_required = True

    # -------------------------------------------------
    # APPROVAL METADATA
    # -------------------------------------------------

    approval_level = fields.Selection(
        [
            ("manager", "Manager"),
            ("gm", "General Manager"),
        ],
        string="Required Approval Level",
        compute="_compute_approval_level",
        store=True,
    )

    approved_by = fields.Many2one(
        "res.users",
        string="Approved By",
        readonly=True,
    )

    approved_date = fields.Datetime(
        string="Approved Date",
        readonly=True,
    )

    # -------------------------------------------------
    # SLA
    # -------------------------------------------------

    sla_deadline = fields.Datetime(
        string="SLA Deadline",
        readonly=True,
        tracking=True,
    )

    is_overdue = fields.Boolean(
        string="Overdue",
        compute="_compute_is_overdue",
        store=True,
    )

    # -------------------------------------------------
    # COMPUTES
    # -------------------------------------------------

    @api.depends("claimed_amount", "policy_id.manager_approval_limit")
    def _compute_approval_level(self):
        for rec in self:
            if not rec.policy_id:
                rec.approval_level = False
            elif rec.claimed_amount <= rec.policy_id.manager_approval_limit:
                rec.approval_level = "manager"
            else:
                rec.approval_level = "gm"

    @api.depends("sla_deadline", "state")
    def _compute_is_overdue(self):
        now = fields.Datetime.now()
        for rec in self:
            rec.is_overdue = (
                rec.state == "submitted" and rec.sla_deadline and now > rec.sla_deadline
            )

    # -------------------------------------------------
    # COMMITTEE VOTE
    # -------------------------------------------------
    def _committee_vote_summary(self):
        self.ensure_one()

        approvals = self.vote_ids.filtered(lambda v: v.decision == "approve")
        rejections = self.vote_ids.filtered(lambda v: v.decision == "reject")

        return {
            "approved": len(approvals),
            "rejected": len(rejections),
        }

    # -------------------------------------------------
    # COMMITTEE ACTIONS (ODOO 19 SAFE)
    # -------------------------------------------------

    def action_committee_vote_approve(self):
        for rec in self:
            rec._committee_vote_internal("approve")

    def action_committee_vote_reject(self):
        for rec in self:
            rec._committee_vote_internal("reject")

    def _evaluate_committee_result(self):
        self.ensure_one()

        summary = self._committee_vote_summary()

        if summary["approved"] >= self.committee_quorum:
            self._close_committee_activities()
            self._finalize_committee_approval()
            return

        if summary["rejected"] >= self.committee_quorum:
            self._close_committee_activities()
            self.state = "rejected"

    def _close_committee_activities(self):
        """
        Auto-close all pending committee activities
        once quorum is reached.
        """
        activities = self.env["mail.activity"].search(
            [
                ("res_model", "=", "insurance.claim"),
                ("res_id", "=", self.id),
                (
                    "activity_type_id",
                    "=",
                    self.env.ref("mail.mail_activity_data_todo").id,
                ),
            ]
        )

        activities.action_done()

    def _finalize_committee_approval(self):
        self.ensure_one()

        # bypass hierarchy — committee already approved
        self.with_context(skip_hierarchy=True).action_approve()

    # -------------------------------------------------
    # COVERAGE LOOKUP
    # -------------------------------------------------

    def _get_coverage_line(self):
        self.ensure_one()

        policy = self.policy_id
        if not policy or not policy.coverage_template_id:
            return False

        return self.env["insurance.coverage.line"].search(
            [
                ("template_id", "=", policy.coverage_template_id.id),
                ("service_id", "=", self.service_id.id),
                ("covered", "=", True),
            ],
            limit=1,
        )

    def _get_reinsurance_contract(self):
        self.ensure_one()

        if not self.policy_id:
            return False

        today = fields.Date.today()

        return self.env["insurance.reinsurance.contract"].search(
            [
                ("policy_id", "=", self.policy_id.id),
                ("active", "=", True),
                ("start_date", "<=", today),
                ("end_date", ">=", today),
            ],
            limit=1,
        )

    # -------------------------------------------------
    # COVERAGE UTILIZATION
    # -------------------------------------------------
    def _update_coverage_utilization(self, amount):
        self.ensure_one()

        coverage = self._get_coverage_line()
        if not coverage:
            return

        coverage.used_amount += amount

    def _reverse_coverage_utilization(self):
        self.ensure_one()

        coverage = self._get_coverage_line()
        if not coverage:
            return

        coverage.used_amount = max(
            coverage.used_amount - (self.approved_amount or 0.0), 0.0
        )

    # -------------------------------------------------
    # POLICY LIMIT CHECK
    # -------------------------------------------------

    def _check_policy_annual_limit(self):
        for rec in self:
            policy = rec.policy_id
            if not policy:
                raise ValidationError("This claim is not linked to a policy.")

            if policy.state != "active":
                raise ValidationError("The linked policy is not active.")

            projected_total = rec.member_id.total_claimed + rec.claimed_amount

            if projected_total > policy.annual_limit:
                raise ValidationError(
                    (
                        "Annual policy limit exceeded.\n\n"
                        "Policy limit: %.2f\n"
                        "Already claimed: %.2f\n"
                        "This claim: %.2f\n"
                        "Projected total: %.2f"
                    )
                    % (
                        policy.annual_limit,
                        rec.member_id.total_claimed,
                        rec.claimed_amount,
                        projected_total,
                    )
                )

    # -------------------------------------------------
    # ACTIONS
    # -------------------------------------------------
    def action_submit(self):
        Attachment = self.env["ir.attachment"]

        for rec in self:
            if rec.state != "draft":
                continue

            attachment_count = Attachment.search_count(
                [
                    ("res_model", "=", "insurance.claim"),
                    ("res_id", "=", rec.id),
                ]
            )

            if attachment_count < 1:
                raise ValidationError(
                    "You must attach at least one medical document before submitting the claim."
                )

            if not rec.policy_id:
                raise ValidationError("This member does not have a policy.")

            if not rec.policy_id.manager_approval_limit:
                raise ValidationError("Policy approval limits are not configured.")

            rec._check_policy_annual_limit()

            coverage = rec._get_coverage_line()
            if not coverage:
                raise ValidationError(
                    f"The service '{rec.service_id.name}' is not covered by this policy."
                )

            if coverage.annual_limit and coverage.remaining_amount <= 0:
                raise ValidationError(
                    "This service has no remaining coverage for the current year."
                )

            # --------------------------------
            # FRAUD EVALUATION (DO NOT BLOCK)
            # --------------------------------
            rec._evaluate_fraud_risk()

            # --------------------------------
            # NORMAL ESCALATION LOGIC
            # --------------------------------
            rec._escalate_if_needed()

            # --------------------------------
            # SLA + SUBMIT
            # --------------------------------
            rec.sla_deadline = fields.Datetime.now() + timedelta(hours=48)
            rec.state = "submitted"

            # --------------------------------
            # COMMITTEE NOTIFICATION (ONLY IF NEEDED)
            # --------------------------------
            if rec.committee_required:
                rec._notify_committee()

    committee_approved_count = fields.Integer(
        compute="_compute_committee_votes", store=False
    )

    committee_rejected_count = fields.Integer(
        compute="_compute_committee_votes", store=False
    )

    committee_has_voted = fields.Boolean(
        compute="_compute_committee_votes", store=False
    )

    def _compute_committee_votes(self):
        for rec in self:
            approvals = rec.vote_ids.filtered(lambda v: v.decision == "approve")
            rejections = rec.vote_ids.filtered(lambda v: v.decision == "reject")

            rec.committee_approved_count = len(approvals)
            rec.committee_rejected_count = len(rejections)
            rec.committee_has_voted = any(
                v.user_id == self.env.user for v in rec.vote_ids
            )

    def _notify_committee(self):
        """
        Notify all Medical Committee members that a claim
        requires committee review.
        """
        self.ensure_one()

        committee_group = self.env.ref(
            "insurance_core.group_insurance_committee", raise_if_not_found=False
        )

        if not committee_group:
            return

        for user in committee_group.user_ids:
            self.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=user.id,
                summary="Medical Committee Review Required",
                note=(
                    f"Claim {self.name} requires Medical Committee review.\n\n"
                    f"Fraud Score: {self.fraud_score}\n"
                    f"Claimed Amount: {self.claimed_amount}"
                ),
            )

    def action_approve(self):
        for rec in self:
            user = self.env.user

            # --------------------------------
            # BASIC GUARDS
            # --------------------------------
            if rec.escalation_level == "committee" and not self.env.context.get(
                "skip_hierarchy"
            ):
                raise ValidationError("This claim requires Medical Committee approval.")

            if rec.create_uid == user:
                raise AccessError("You cannot approve your own claim.")

            if rec.state != "submitted":
                raise ValidationError("Only submitted claims can be approved.")

            if rec.fraud_flag:
                raise ValidationError(
                    "This claim is flagged for fraud review and cannot be approved."
                )
            # --------------------------------
            # ACCOUNTING PREFLIGHT CHECK
            # --------------------------------
            rec._accounting_preflight_check()
            # --------------------------------
            # ESCALATION AUTHORITY (SOURCE OF TRUTH)
            # --------------------------------
            if rec.escalation_level == "manager":
                if not user.has_group("insurance_core.group_insurance_manager"):
                    raise AccessError("Manager approval required.")

            elif rec.escalation_level == "gm":
                if not user.has_group("insurance_core.group_insurance_gm"):
                    raise AccessError("General Manager approval required.")

            elif rec.escalation_level == "committee":
                raise ValidationError("Medical Committee decision required.")

            # --------------------------------
            # COVERAGE VALIDATION
            # --------------------------------
            coverage = rec._get_coverage_line()
            if not coverage:
                raise ValidationError("Coverage rule not found.")

            # --------------------------------
            # PER-CLAIM LIMIT
            # --------------------------------
            approved_base = rec.claimed_amount
            if coverage.per_claim_limit:
                approved_base = min(approved_base, coverage.per_claim_limit)

            # --------------------------------
            # ANNUAL SERVICE LIMIT
            # --------------------------------
            year_start = fields.Date.to_date(f"{fields.Date.today().year}-01-01")
            year_end = fields.Date.to_date(f"{fields.Date.today().year}-12-31")

            previous_claims = self.search(
                [
                    ("member_id", "=", rec.member_id.id),
                    ("service_id", "=", rec.service_id.id),
                    ("state", "=", "approved"),
                    ("approved_date", ">=", year_start),
                    ("approved_date", "<=", year_end),
                ]
            )

            already_used = sum(previous_claims.mapped("approved_amount"))

            if coverage.annual_limit:
                remaining = coverage.annual_limit - already_used
                if remaining <= 0:
                    raise ValidationError(
                        "Annual coverage limit has already been fully used."
                    )
                approved_base = min(approved_base, remaining)

            # --------------------------------
            # APPLY CO-PAY
            # --------------------------------
            copay = coverage.copay_percentage or 0.0
            insurer_share = approved_base * (1 - (copay / 100))
            reinsurer_share = 0.0

            # --------------------------------
            # REINSURANCE
            # --------------------------------
            reinsurance = rec._get_reinsurance_contract()
            if reinsurance:
                retention = reinsurance.retention_amount

                if insurer_share > retention:
                    reinsurer_share = insurer_share - retention
                    insurer_share = retention

                if reinsurance.max_coverage_amount:
                    reinsurer_share = min(
                        reinsurer_share, reinsurance.max_coverage_amount
                    )

                rec.reinsurance_contract_id = reinsurance.id

            # --------------------------------
            # FINAL SAVE
            # --------------------------------
            rec.insurer_share = insurer_share
            rec.reinsurer_share = reinsurer_share
            rec.approved_amount = insurer_share + reinsurer_share
            rec.approved_by = user
            rec.approved_date = fields.Datetime.now()
            # AUTO-CREATE ACCOUNTING ENTRY
            rec._create_accounting_entry()
            rec.state = "approved"
            # rec._create_payment()

            # --------------------------------
            # UTILIZATION
            # --------------------------------
            rec._update_coverage_utilization(insurer_share)

    @api.model
    def create(self, vals_list):
        # Odoo may send a dict OR a list → normalize
        if isinstance(vals_list, dict):
            vals_list = [vals_list]

        for vals in vals_list:
            if vals.get("name", "New") == "New":
                vals["name"] = (
                    self.env["ir.sequence"].next_by_code("insurance.claim") or "New"
                )

        return super().create(vals_list)

    # --------------------------------------------------
    # JOURNAL HELPER
    # --------------------------------------------------
    def _get_journal(self, journal_type):
        """
        Safely fetch an accounting journal for the claim's company
        """
        self.ensure_one()

        journal = self.env["account.journal"].search(
            [
                ("type", "=", journal_type),
                ("company_id", "=", self.company_id.id),
            ],
            limit=1,
        )

        if not journal:
            raise ValidationError(
                f"No {journal_type} journal configured for company "
                f"{self.company_id.name}"
            )

        return journal

    def _get_payee_partner(self):
        self.ensure_one()

        if self.payee_type == "provider":
            if not self.provider_id.partner_id:
                raise ValidationError(
                    "Medical Provider has no accounting partner configured."
                )
            return self.provider_id.partner_id

        if self.payee_type == "member":
            if not self.member_id.partner_id:
                raise ValidationError("Member has no accounting partner configured.")
            return self.member_id.partner_id

    # -----------------------------
    # MAIN ENTRY POINT (BUTTON)
    # -----------------------------
    payment_move_id = fields.Many2one(
        "account.move", string="Accounting Entry", readonly=True
    )
    payment_state = fields.Selection(
        [("not_paid", "Not Paid"), ("paid", "Paid")], default="not_paid", tracking=True
    )

    def _create_payment(self):
        self.ensure_one()

        if not self.payment_move_id:
            raise ValidationError("No invoice exists to pay.")

        if self.payment_state == "paid":
            return

        invoice = self.payment_move_id
        partner = invoice.partner_id

        journal = self._get_journal("bank")

        payment = self.env["account.payment"].create(
            {
                "payment_type": "outbound",
                "partner_type": (
                    "supplier" if self.payee_type == "provider" else "customer"
                ),
                "partner_id": partner.id,
                "amount": invoice.amount_total,
                "currency_id": invoice.currency_id.id,
                "date": fields.Date.today(),
                "journal_id": journal.id,
            }
        )

        payment.action_post()
        payment.move_id.ref = f"Payment for Claim {self.name}"

        # Reconcile automatically
        (invoice.line_ids + payment.move_id.line_ids).filtered(
            lambda l: l.account_id
            == invoice.line_ids.filtered("account_id")[0].account_id
        ).reconcile()

        self.payment_state = "paid"

    def action_create_payment(self):
        self.ensure_one()

        if not self.payment_move_id:
            raise ValidationError("No accounting document exists for this claim.")

        return {
            "type": "ir.actions.act_window",
            "res_model": "account.move",
            "res_id": self.payment_move_id.id,
            "view_mode": "form",
        }

    def action_check_accounting(self):
        for rec in self:
            rec._accounting_preflight_check()

    def _create_accounting_entry(self):
        self.ensure_one()

        if self.payment_move_id:
            return self.payment_move_id

        if not self.approved_amount or self.approved_amount <= 0:
            raise ValidationError("Approved amount must be greater than zero.")

        partner = self._get_payee_partner()

        if self.payee_type == "provider":
            move_type = "in_invoice"
            expense_account = (
                self.provider_id.expense_account_id
                or self.company_id.insurance_claim_expense_account_id
            )

            if not expense_account:
                raise ValidationError("Missing expense account configuration.")

            if not partner.property_account_payable_id:
                default_payable = self.company_id.partner_id.property_account_payable_id
                if not default_payable:
                    raise ValidationError(
                        "Company has no default payable account configured."
                    )
                partner.property_account_payable_id = default_payable

        else:
            move_type = "out_refund"
            expense_account = self.company_id.insurance_claim_expense_account_id

            if not expense_account:
                raise ValidationError("Missing company expense account.")

            if not partner.property_account_receivable_id:
                default_receivable = (
                    self.company_id.partner_id.property_account_receivable_id
                )
                if not default_receivable:
                    raise ValidationError(
                        "No default receivable account is configured on the company partner."
                    )
                partner.property_account_receivable_id = default_receivable

        move = self.env["account.move"].create(
            {
                "move_type": move_type,
                "partner_id": partner.id,
                "company_id": self.company_id.id,
                "invoice_date": fields.Date.today(),
                "ref": f"Insurance Claim {self.name}",
                "invoice_line_ids": [
                    (
                        0,
                        0,
                        {
                            "name": f"Insurance Claim {self.name}",
                            "quantity": 1,
                            "price_unit": self.approved_amount,
                            "account_id": expense_account.id,
                        },
                    )
                ],
            }
        )

        move.action_post()
        self.payment_move_id = move.id
        return move

    def action_committee_approve(self):
        for rec in self:
            rec._committee_vote_internal("approve")

    def action_committee_reject(self):
        for rec in self:
            rec._committee_vote_internal("reject")

    def _committee_vote_internal(self, decision):
        self.ensure_one()

        user = self.env.user

        if not user.has_group("insurance_core.group_insurance_committee"):
            raise AccessError("Only committee members can vote.")

        if self.state != "submitted" or not self.committee_required:
            raise ValidationError("This claim is not under committee review.")

        existing = self.vote_ids.filtered(lambda v: v.user_id == user)
        if existing:
            raise ValidationError("You have already voted on this claim.")

        self.env["insurance.claim.vote"].create(
            {
                "claim_id": self.id,
                "user_id": user.id,
                "decision": decision,
            }
        )

        self._evaluate_committee_result()

    def action_reject(self):
        for rec in self:
            if rec.payment_move_id and rec.payment_move_id.state == "posted":
                reversal = rec.payment_move_id._reverse_moves(
                    date=fields.Date.today(),
                    reason=f"Claim {rec.name} rejected",
                    journal=rec.payment_move_id.journal_id,
                )
                rec.payment_move_id = False
                rec.payment_state = "not_paid"

            if rec.state == "approved":
                rec._reverse_coverage_utilization()

            if rec.payment_state == "paid":
                raise ValidationError(
                    "This claim has already been paid. "
                    "Please reverse the payment before rejecting."
                )

            rec.state = "rejected"

    # -------------------------------------------------
    # CRON
    # -------------------------------------------------

    @api.model
    def cron_update_overdue_claims(self):
        now = fields.Datetime.now()
        claims = self.search(
            [
                ("state", "=", "submitted"),
                ("sla_deadline", "<", now),
            ]
        )
        claims._compute_is_overdue()

    # ---------------------------------
    # REINSURANCE SPLIT
    # ---------------------------------

    insurer_share = fields.Float(string="Insurer Share", readonly=True)

    reinsurer_share = fields.Float(string="Reinsurer Share", readonly=True)

    reinsurance_contract_id = fields.Many2one(
        "insurance.reinsurance.contract", string="Reinsurance Contract", readonly=True
    )

    def _accounting_preflight_check(self):
        self.ensure_one()

        company = self.company_id

        # -------------------------------------------------
        # COMPANY CHECKS
        # -------------------------------------------------
        if not company:
            raise ValidationError("Claim has no company.")

        if not company.partner_id.property_account_payable_id:
            raise ValidationError(
                "Company accounting is incomplete.\n\n"
                "Missing: Company Partner Payable Account.\n\n"
                "Fix:\n"
                "Settings → Companies → Your Company → Partner → Accounting."
            )

        if not company.partner_id.property_account_receivable_id:
            raise ValidationError(
                "Company accounting is incomplete.\n\n"
                "Missing: Company Partner Receivable Account."
            )

        purchase_journal = self.env["account.journal"].search(
            [
                ("type", "=", "purchase"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not purchase_journal:
            raise ValidationError(
                "Accounting configuration missing.\n\n"
                "No Purchase Journal found.\n\n"
                "Fix:\n"
                "Accounting → Configuration → Journals → Create Purchase journal."
            )

        bank_journal = self.env["account.journal"].search(
            [
                ("type", "=", "bank"),
                ("company_id", "=", company.id),
            ],
            limit=1,
        )
        if not bank_journal:
            raise ValidationError(
                "Accounting configuration missing.\n\n"
                "No Bank Journal found.\n\n"
                "Fix:\n"
                "Accounting → Configuration → Journals → Create Bank journal."
            )

        # -------------------------------------------------
        # PAYEE CHECKS
        # -------------------------------------------------
        partner = self._get_payee_partner()

        if self.payee_type == "provider":
            if not partner.property_account_payable_id:
                raise ValidationError(
                    "Provider accounting is incomplete.\n\n"
                    "Missing: Provider Partner Payable Account.\n\n"
                    "Fix:\n"
                    "Open Provider → Partner → Accounting."
                )

            expense_account = (
                self.provider_id.expense_account_id
                or company.insurance_claim_expense_account_id
            )
            if not expense_account:
                raise ValidationError(
                    "Missing expense account.\n\n"
                    "Fix:\n"
                    "• Set Expense Account on Provider, OR\n"
                    "• Set Default Insurance Claim Expense Account on Company."
                )

        else:  # member reimbursement
            if not partner.property_account_receivable_id:
                raise ValidationError(
                    "Member accounting is incomplete.\n\n"
                    "Missing: Member Partner Receivable Account."
                )

            if not company.insurance_claim_expense_account_id:
                raise ValidationError(
                    "Missing company expense account for member reimbursements."
                )
