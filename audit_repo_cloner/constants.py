ISSUE_TEMPLATE = """---
name: Finding
about: Description of the finding
title: ''
labels: ''
assignees: ''
---

**Description:**

**Impact:**

**Proof of Concept:**

**Recommended Mitigation:**

**[Project]:** 

**Cyfrin:**"""

DEFAULT_LABELS = [
    "bug",
    "duplicate",
    "enhancement",
    "invalid",
    "question",
    "wontfix",
    "good first issue",
    "help wanted",
    "documentation",
]


SEVERITY_DATA = [
    {"name": "Severity: Critical Risk", "color": "ff0000"},
    {"name": "Severity: High Risk", "color": "B60205"},
    {"name": "Severity: Medium Risk", "color": "D93F0B"},
    {"name": "Severity: Low Risk", "color": "FBCA04"},
    {"name": "Severity: Informational", "color": "1D76DB"},
    {"name": "Severity: Gas Optimization", "color": "B4E197"},
    {"name": "Report Status: Open", "color": "5319E7"},
    {"name": "Report Status: Acknowledged", "color": "BFA8DC"},
    {"name": "Report Status: Resolved", "color": "0E8A16"},
    {"name": "Report Status: Closed", "color": "bfdadc"},
]
TRELLO_LABELS = [
    "Archived",
    "Needs Discussion",
    "Self-Validated",
    "Co-Validated",
    "Report Ready",
]
TRELLO_COLUMNS = ["Archive", "Ideas", "Findings", "Peer Reviewed", "Report"]
