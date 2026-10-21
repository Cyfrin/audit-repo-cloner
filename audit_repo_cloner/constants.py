ISSUE_TEMPLATE = """---
name: Finding
about: Description of the finding
title: ''
labels: 'Cyfrin: Draft'
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


CYFRIN_LABEL_PREFIX = "Cyfrin: "
PROTOCOL_LABEL_PREFIX = "Protocol: "

# Each label family has its own colors: Severity reds to blues, Cyfrin purples darkening as a finding
# progresses from Draft to its final status, Protocol browns and teals
SEVERITY_DATA = [
    {"name": "Severity: Critical Risk", "color": "ff0000"},
    {"name": "Severity: High Risk", "color": "B60205"},
    {"name": "Severity: Medium Risk", "color": "D93F0B"},
    {"name": "Severity: Low Risk", "color": "FBCA04"},
    {"name": "Severity: Informational", "color": "1D76DB"},
    {"name": "Severity: Gas Optimization", "color": "B4E197"},
    {"name": "Cyfrin: Draft", "color": "E4DAF7"},
    {"name": "Cyfrin: Peer Reviewed", "color": "A784E0"},
    {"name": "Cyfrin: Partially Resolved", "color": "7349C2"},
    {"name": "Cyfrin: Acknowledged", "color": "5B3A9E"},
    {"name": "Cyfrin: Resolved", "color": "3B1F78"},
    {"name": "Protocol: Needs Response", "color": "D9B48F"},
    {"name": "Protocol: Will Fix", "color": "5FB3A9"},
    {"name": "Protocol: Proposed Fix", "color": "1F7A70"},
    {"name": "Protocol: Acknowledged", "color": "C9A27E"},
    {"name": "Protocol: Proposed Invalid", "color": "6B4226"},
    {"name": "BAD ISSUE FORMATTING", "color": "4A002A"},
]
