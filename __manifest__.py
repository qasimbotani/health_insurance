{
    "name": "Health Insurance",
    "version": "1.0",
    "category": "Insurance",
    "summary": "Core Health Insurance Management",
    "author": "Qasim",
    "depends": ["base", "mail", "account", "web"],
    "data": [
        # -------------------------
        # SECURITY
        # -------------------------
        "security/security.xml",
        "security/groups.xml",
        "security/record_rules.xml",
        "security/ir.model.access.csv",
        # -------------------------
        # SEQUENCES & DATA
        # -------------------------
        "data/sequence.xml",
        "data/member_sequence.xml",
        # -------------------------
        # CRONS
        # -------------------------
        "data/policy_cron.xml",
        "data/member_cron.xml",
        "data/cron.xml",
        # -------------------------
        # REPORTS
        # -------------------------
        "reports/paperformat.xml",
        "reports/report_member_welcome_pack.xml",
        "reports/member_id_card.xml",
        "reports/report_actions.xml",
        # -------------------------
        # ACTIONS + VIEWS
        # -------------------------
        "views/policy_coverage_utilization_action.xml",
        "views/policy_views.xml",
        "views/member_views.xml",
        "views/member_document_views.xml",
        "views/claim_views.xml",
        "views/provider_views.xml",
        "views/coverage_template_views.xml",
        "views/service_views.xml",
        "views/reinsurance_contract_views.xml",
        "views/reinsurance_bordereau_views.xml",
        "views/reinsurance_bordereau_line_views.xml",
        "views/reinsurance_settlement_views.xml",
        "views/committee_dashboard_views.xml",
        "views/res_company_views.xml",
        # -------------------------
        # MENUS ALWAYS LAST
        # -------------------------
        "views/menu.xml",
    ],
    "installable": True,
    "application": True,
}
