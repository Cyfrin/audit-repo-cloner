# Audit Repository Cloner

This repository contains a Python package to clone a repo and automatically prepare it for [Cyfrin](https://www.cyfrin.io/) audit report generation.

# What it does

It will take the following steps:
1. Take one or more `source` repositories you want to set up for audit
2. Take the `target` repository name you want to use for the private repository
3. Add an `issue_template` to the repo, so issues can be formatted as audit findings, like:

```
**Description:**
**Impact:**
**Proof of Concept:**
**Recommended Mitigation:**
**[Project]:**
**Cyfrin:**
```

4. Update labels to label issues based on severity and status
5. Add each source repository as a git submodule at the specified commit hash
6. Create a tag for each source repository at the given commit hash (full SHA)
7. Create branches for each of the auditors participating
8. Create a branch for the final report
9. Add the [report-generator-template](https://github.com/Cyfrin/report-generator-template) to the repo to make it easier to compile the report, and add a button in GitHub actions to re-generate the report on-demand
10. Attempt to set up a GitHub project board

Note: Changes to `report-generator-template` can be pulled into the generated repo by running:
```bash
git subtree pull --prefix cyfrin-report/report-generator-template https://github.com/Cyfrin/report-generator-template main --squash
```

# Getting Started

## Requirements

- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
  - You'll know you did it right if you can run `git --version` and you see a response like `git version x.x.x`
- [Python 3.7 or higher](https://www.python.org/downloads/)
  - You'll know you've installed python right if you can run:
    - `python --version` or `python3 --version` and get an output like: `Python 3.x.x`
- [pip](https://pypi.org/project/pip/)
  - You'll know you did it right if you can run `pip --version` or `pip3 --version` and get an output like `pip x.x from /some/path/here (python x.x)`

## Installation

To install from source:

```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

To install from pipx:
```bash
pipx install audit-repo-cloner
```

And if installing from source with pipx package already installed, install in editable mode:
```bash
pip install -e .
```

You'll know you've installed it correctly if you can run:

```bash
audit_repo_cloner --version
```

## Getting a GitHub token

To use this, you'll need a [github personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token). Please view the docs to set one up.

You can then set it as an environment variable or input it via the CLI:

```bash
export GITHUB_ACCESS_TOKEN=xxxxxx
```

Note: this access token is only used to create the repo initially. To allow the GitHub Action to run the report generator (fetching issues) in CI, be sure to set appropriate permissions for the global [`GITHUB_TOKEN` secret](https://docs.github.com/en/actions/security-guides/automatic-token-authentication).

# Usage

## Using config.json for multiple repositories

The tool supports cloning multiple repositories into a single audit repository using git submodules. To use this feature, create a `config.json` file based on the provided example:

```bash
cp config.json.example config.json
```

Edit the `config.json` file to include your repository details:

```json
{
  "targetRepoName": "audit-2024-05-myproject",
  "projectTitle": "[Audit] My Project (2024-05)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://github.com/username/protocol-repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12",
      "subFolder": "protocol"
    },
    {
      "sourceUrl": "https://github.com/username/frontend-repo",
      "commitHash": "fedcba0987654321fedcba0987654321fedcba09",
      "subFolder": "frontend"
    }
  ]
}
```

Then run the tool:

```bash
audit_repo_cloner --config-file config.json --github-token YOUR_TOKEN --organization YOUR_ORG
```

Or simply:

```bash
audit_repo_cloner
```

This will prompt for any missing information and use values from your `.env` file and `config.json`.

## Help

```bash
audit_repo_cloner --help
```
