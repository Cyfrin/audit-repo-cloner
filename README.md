# Audit Repository Cloner

A Python package to clone a repo and automatically prepare it for [Cyfrin](https://www.cyfrin.io/) audit report generation.

## Features

- Clone one or more source repositories into a target repository
- Add issue templates for audit findings
- Configure labels for severity and status
- Add source repositories as git subtrees
- Create tags for each source repository
- Create branches for auditors and final report
- Add [report-generator-template](https://github.com/Cyfrin/report-generator-template)
- Set up GitHub project board
- Remove GitHub Actions from source repositories for security

## Quick Start

1. Install requirements:
```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Get a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) and add it to the `.env` file:
```bash
cp .env.example .env
```

3. Create a `config.json` file:
```bash
cp config.json.example config.json
```

4. Edit `config.json` with your repository details:
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
    }
  ]
}
```

5. Run the tool:
```bash
# specifying github token and organization in the cmd
python -m audit_repo_cloner.create_audit_repo --config-file config.json --github-token YOUR_TOKEN --organization YOUR_ORG
# using .env file for github token and org
python -m audit_repo_cloner.create_audit_repo --config-file config.json
# if config file is not specified, config.json is used by default
python -m audit_repo_cloner.create_audit_repo
```

## Development

1. Set up development environment:
```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

2. Install pre-commit hooks:
```bash
pre-commit install
pre-commit run --all-files
```