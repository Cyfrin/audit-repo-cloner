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
- Remove GitHub Actions and GitLab CI from source repositories for security

## Quick Start

1. Install UV (if not already installed):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

2. Clone and install:
```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
uv sync
```

3. Get a [GitHub personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token) and either set it in environment variable `GITHUB_ACCESS_TOKEN` or add it to the `.env` file:
```bash
cp .env.example .env
```

4. Create a `config.json` file:
```bash
# only 1 repo
cp config.1repo.json.example config.json

# 2 or more repos
cp config.2repo.json.example config.json

# GitLab source repo
cp config.gitlab.json.example config.json

# mixed GitHub + GitLab repos
cp config.mixed.json.example config.json
```

5. Edit `config.json` with your repository details; one repo with no subfolder in the generated repo:
```json
{
  "targetRepoName": "audit-2026-02-myproject",
  "projectTitle": "[Audit] My Project (2026-02)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://github.com/username/protocol-repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12"
    }
  ]
}
```

Two repos each with a subfolder in the generated repo:
```json
{
  "targetRepoName": "audit-2026-02-myproject",
  "projectTitle": "[Audit] My Project (2026-02)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://github.com/username/main-repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12",
      "subFolder": "main"
    },
    {
      "sourceUrl": "https://github.com/username/periphery-repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12",
      "subFolder": "periphery"
    }
  ]
}
```

6. Run the tool:
```bash
# github token in env variable and config.json input file
./run_repo_cloner

# specifying github token and organization in the cmd
uv run python -m audit_repo_cloner.create_audit_repo --config-file config.json --github-token YOUR_TOKEN --organization YOUR_ORG

# using .env file for github token and org
uv run python -m audit_repo_cloner.create_audit_repo --config-file config.json

# if config file is not specified, config.json is used by default
uv run python -m audit_repo_cloner.create_audit_repo
```

## GitLab Support

Source repositories can be hosted on GitLab (gitlab.com or self-hosted) in addition to GitHub. The tool auto-detects the platform from the URL. Mixed GitHub and GitLab repositories are supported in the same config.

**Note:** A GitHub token (`GITHUB_ACCESS_TOKEN`) is always required since the target audit repository is created on GitHub.

### Step 1: Create a GitLab Personal Access Token

Log into your GitLab instance, then go to **User Settings > Access Tokens** (or navigate to `https://your-gitlab-instance/-/user_settings/personal_access_tokens`). Create a token with at least the `read_repository` scope and copy the token value.

### Step 2: Add the token to `.env`

```bash
GITLAB_ACCESS_TOKEN=glpat-your-token-here
```

Or pass it via CLI with `--gitlab-token YOUR_TOKEN`.

### Cloning from gitlab.com

URLs containing "gitlab" in the hostname are auto-detected. Just use the GitLab URL in `sourceUrl`:

```json
{
  "targetRepoName": "audit-2026-04-myproject",
  "projectTitle": "[Audit] My Project (2026-04)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://gitlab.com/group/subgroup/repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12"
    }
  ]
}
```

Then run:
```bash
./run_repo_cloner
```

### Cloning from self-hosted GitLab

Self-hosted instances whose hostnames contain "gitlab" (e.g. `gitlab.mycompany.com`) are also auto-detected and work the same way as above.

For self-hosted instances whose hostnames **do not** contain "gitlab" (e.g. `git.mycompany.com`), you have two options:

**Option A: Use `sourceType` in config (simplest for one-off use)**

```json
{
  "targetRepoName": "audit-2026-04-myproject",
  "projectTitle": "[Audit] My Project (2026-04)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://git.mycompany.com/group/repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12",
      "sourceType": "gitlab"
    }
  ]
}
```

**Option B: Use `GITLAB_HOSTS` env var (better for repeated use)**

Add the hostname to `.env` so it's always auto-detected:
```bash
GITLAB_ACCESS_TOKEN=glpat-your-token-here
GITLAB_HOSTS=git.mycompany.com
```

Then `sourceType` is not needed in the config:
```json
{
  "targetRepoName": "audit-2026-04-myproject",
  "projectTitle": "[Audit] My Project (2026-04)",
  "auditors": "auditor1 auditor2 auditor3",
  "repositories": [
    {
      "sourceUrl": "https://git.mycompany.com/group/repo",
      "commitHash": "abcdef1234567890abcdef1234567890abcdef12"
    }
  ]
}
```

Multiple hostnames can be comma-separated: `GITLAB_HOSTS=git.mycompany.com,code.internal.io`

### Additional CLI Options

```bash
uv run python -m audit_repo_cloner.create_audit_repo \
  --config-file config.json \
  --github-token YOUR_GITHUB_TOKEN \
  --gitlab-token YOUR_GITLAB_TOKEN \
  --gitlab-hosts git.mycompany.com \
  --organization YOUR_ORG
```

See `config.gitlab.json.example` and `config.mixed.json.example` for more examples.

## Development

1. Set up development environment:
```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
uv sync --group dev
```

2. Install pre-commit hooks:
```bash
uv run pre-commit install
uv run pre-commit run --all-files
```