from __future__ import annotations

from datetime import date

from audit_repo_cloner.audit_config import AuditConfig
from audit_repo_cloner.create_audit_repo import fill_report_source

# Trimmed copy of report-generator-template/source/summary_information.conf
SUMMARY_TEMPLATE = """[summary]
project_name = PROJECT_NAME
report_version = 1.0
team_name = TEAM_NAME
team_website = https://madeupname.finance
private_github = https://github.com/Cyfrin/madeupname.git
project_github = https://github.com/madeupnamefinance/madeupname.git
commit_hash = 78d38753b2042d7813132f26e5573c6699b605ef
fix_commit_hash =
project_github_2 =
commit_hash_2 =
review_timeline = Sep 7th - Sep 11th, 2026
review_methods = Manual Review
project_number =
"""


def make_config():
    return AuditConfig(
        team_name="Securitize",
        project_name="Tempo Async Vault",
        team_website="https://securitize.io",
        start_date=date(2026, 10, 4),
        end_date=date(2026, 10, 5),
        scope_markdown="The audit scope was limited to:\n```\ncontracts/Vault.sol\n```",
        auditors=["Kage", "BengalCatBalu"],
        repositories=[
            {"sourceUrl": "https://github.com/org/main", "commitHash": "a" * 40},
            {"sourceUrl": "https://github.com/org/periphery", "commitHash": "b" * 40},
        ],
    )


def test_fills_report_source(tmp_path):
    (tmp_path / "summary_information.conf").write_text(SUMMARY_TEMPLATE)
    (tmp_path / "lead_auditors.md").write_text("Auditor1\nAuditor2\nTeam1\n")
    (tmp_path / "audit_scope.md").write_text("TODO")

    fill_report_source(str(tmp_path), make_config(), "Cyfrin", "audit-2026-10-securitize-tempo-async-vault", "Manual Review, Formal Verification")

    summary = (tmp_path / "summary_information.conf").read_text()
    assert "project_name = Tempo Async Vault\n" in summary
    assert "team_name = Securitize\n" in summary
    assert "team_website = https://securitize.io\n" in summary
    assert "private_github = https://github.com/Cyfrin/audit-2026-10-securitize-tempo-async-vault.git\n" in summary
    assert "project_github = https://github.com/org/main\n" in summary
    assert f"commit_hash = {'a' * 40}\n" in summary
    assert "project_github_2 = https://github.com/org/periphery\n" in summary
    assert f"commit_hash_2 = {'b' * 40}\n" in summary
    assert "review_timeline = Oct 4th - Oct 5th, 2026\n" in summary
    assert "review_methods = Manual Review, Formal Verification\n" in summary
    # untouched fields
    assert "report_version = 1.0\n" in summary
    assert "fix_commit_hash =\n" in summary
    assert "project_number =\n" in summary

    assert (tmp_path / "lead_auditors.md").read_text() == "Kage\nBengalCatBalu\n"
    assert (tmp_path / "audit_scope.md").read_text() == make_config().scope_markdown
