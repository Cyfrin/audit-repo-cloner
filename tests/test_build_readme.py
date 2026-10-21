from __future__ import annotations

import re
from urllib.parse import parse_qs, urlparse

from audit_repo_cloner.create_audit_repo import build_readme


def _links() -> dict[str, str]:
    """Maps each README filter link title to its decoded issue search query."""
    readme = build_readme("Cyfrin", "audit-2026-10-test")
    links = {}
    for title, url in re.findall(r"^- \[([^\]]+)\]\(([^)]+)\)", readme, flags=re.MULTILINE):
        parsed = urlparse(url)
        assert parsed.netloc == "github.com" and parsed.path == "/Cyfrin/audit-2026-10-test/issues"
        links[title] = parse_qs(parsed.query)["q"][0]
    return links


def test_findings_to_review_uses_needs_response_label():
    query = _links()["Findings to review"]
    assert query == 'is:issue is:open label:"Protocol: Needs Response" sort:created-asc'


def test_other_links():
    links = _links()
    assert '-label:"Cyfrin: Draft"' in links["All peer-reviewed findings"]
    assert 'label:"Cyfrin: Peer Reviewed" label:"Protocol: Proposed Fix"' in links["Fixes awaiting verification"]
    assert 'label:"Cyfrin: Peer Reviewed" label:"Protocol: Proposed Invalid"' in links["Disputed findings"]
    assert 'label:"Cyfrin: Draft"' in links["Drafts awaiting peer review"]
