from odoo import models, fields


class InsuranceFraudHeatmap(models.Model):
    _name = "insurance.fraud.heatmap"
    _description = "Insurance Fraud Heatmap"
    _auto = False

    service_id = fields.Many2one("insurance.service", string="Service")
    provider_id = fields.Many2one("insurance.provider", string="Provider")
    claim_count = fields.Integer(string="Claims")
    avg_fraud_score = fields.Float(string="Avg Fraud Score")

    def init(self):
        self.env.cr.execute(
            """
            CREATE OR REPLACE VIEW insurance_fraud_heatmap AS (
                SELECT
                    MIN(c.id) AS id,
                    c.service_id,
                    c.provider_id,
                    COUNT(*) AS claim_count,
                    AVG(c.fraud_score) AS avg_fraud_score
                FROM insurance_claim c
                WHERE c.fraud_flag = TRUE
                GROUP BY c.service_id, c.provider_id
            )
        """
        )
