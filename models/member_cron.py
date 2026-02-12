from odoo import models, fields, api
from datetime import timedelta


class InsuranceMemberCron(models.Model):
    _inherit = "insurance.member"

    @api.model
    def cron_remind_missing_documents(self):

        members = self.search(
            [
                ("state", "=", "pending_documents"),
            ]
        )

        for member in members:
            if not member.underwriting_complete:
                member.activity_schedule(
                    "mail.mail_activity_data_todo",
                    summary="Missing Underwriting Documents",
                    note="Member still missing required documents.",
                    user_id=self.env.ref("insurance_core.group_underwriter")
                    .users[:1]
                    .id,
                )
