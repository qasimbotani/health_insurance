from odoo import models, fields


class InsuranceMemberDocument(models.Model):
    _name = "insurance.member.document"
    _description = "Member Underwriting Document"
    _inherit = ["mail.thread"]

    member_id = fields.Many2one(
        "insurance.member",
        required=True,
        ondelete="cascade",
    )

    document_type = fields.Selection(
        [
            ("id", "ID Copy"),
            ("application", "Signed Application Form"),
            ("medical", "Medical Questionnaire"),
            ("address", "Proof of Address"),
            ("lab", "Medical Lab Report"),
        ],
        required=True,
        tracking=True,
    )

    attachment_id = fields.Many2one(
        "ir.attachment",
        string="Attachment",
        required=True,
    )

    verified = fields.Boolean(
        string="Verified by Underwriting",
        default=False,
        tracking=True,
    )

    verified_by = fields.Many2one(
        "res.users",
        readonly=True,
    )

    verified_date = fields.Datetime(
        readonly=True,
    )
