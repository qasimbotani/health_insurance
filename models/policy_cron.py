from odoo import models, api


class InsurancePolicyCron(models.AbstractModel):
    _name = "insurance.policy.cron"
    _description = "Insurance Policy Cron Jobs"

    @api.model
    def cron_update_policy_states(self):
        """
        Daily cron:
        - Expire policies past end date
        - Mark policies as expiring (≤ 90 days)
        """

        policies = self.env["insurance.policy"].search(
            [
                ("state", "in", ("active", "expiring")),
                ("end_date", "!=", False),
            ]
        )

        policies._auto_update_policy_state()
