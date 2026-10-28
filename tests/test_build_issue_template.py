from __future__ import annotations

from audit_repo_cloner.create_audit_repo import build_issue_template


def test_project_placeholder_replaced_with_team_name():
    template = build_issue_template("Securitize")
    assert "[Project]" not in template
    assert template.endswith("**Securitize:**\n\n**Cyfrin:**")
