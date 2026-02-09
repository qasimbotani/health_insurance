from odoo import models

class AccountMove(models.Model):
    _inherit = 'account.move'

    def write(self, vals):
        res = super().write(vals)

        if vals.get('payment_state') == 'paid':
            claims = self.env['insurance.claim'].search([
                ('payment_move_id', 'in', self.ids)
            ])
            claims.write({'payment_state': 'paid'})

        return res
