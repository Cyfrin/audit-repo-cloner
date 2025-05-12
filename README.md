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
pip install -e .  # Install from pyproject.toml
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
pip install -e ".[dev]"  # Install with development dependencies
```

2. Install pre-commit hooks:
```bash
pre-commit install
pre-commit run --all-files
```

## Testing

### Prerequisites

To run the tests, especially integration tests, you'll need:

- Python 3.8 or higher
- A GitHub account with access to an organization where you can create test repositories
- A GitHub personal access token with appropriate permissions:
  - `repo` (full control of repositories)
  - `workflow` (update GitHub Action workflows)
  - `delete_repo` (for cleanup)

### Set Up Environment Variables

Set up environment variables for the GitHub integration tests:

```bash
export TEST_GITHUB_TOKEN=your_github_token
export TEST_GITHUB_ORG=your_organization_name
```

### Running Tests

```bash
# Run all tests
pytest

# Run only unit tests
pytest tests/ -k "not integration"

# Run only integration tests
pytest tests/integration/

# Run with coverage report
pytest --cov=audit_repo_cloner
```

### Important Notes

- **Repository Creation**: The integration tests create real GitHub repositories. Always use a test organization.
- **Cleanup**: The tests attempt to clean up all created repositories, but you should verify this.
- **Rate Limits**: Be aware of GitHub API rate limits when running many tests.

For detailed information about the test suite structure and how to add new tests, see the [tests/README.md](tests/README.md) file.

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.