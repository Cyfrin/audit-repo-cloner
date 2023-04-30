from github import GithubException


def copy_issue_template(repo):
    issue_template = '''---
name: Finding
about: Description of the finding
title: ''
labels: ''
assignees: ''
---

**Description:**

**Proof of Concept:**

**Impact:**

**Recommended Mitigation:**

**[Project]:** 

**Cyfrin:**'''

    # Get the existing finding.md file, if it exists
    try:
        finding_file = repo.get_contents(".github/ISSUE_TEMPLATE/finding.md")
    except GithubException as e:
        finding_file = None

    # If finding.md already exists, update its contents. Otherwise, create the file.
    if finding_file is not None:
        # repo.update_file(finding_file.path, "update: finding.md", issue_template, finding_file.sha)
        pass
    else:
        repo.create_file(".github/ISSUE_TEMPLATE/finding.md", "finding.md", issue_template)
