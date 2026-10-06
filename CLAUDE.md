# CLAUDE.md

## What this is

Python CLI tool that creates private GitHub audit repositories for Cyfrin clients. It clones source repos (GitHub/GitLab) as git subtrees, strips CI/CD, sets up audit-specific labels/issues/branches, adds a report-generator-template, and configures a GitHub project board.

## Running

```bash
# Run the tool (reads config.json by default)
./run_repo_cloner

# Or directly
uv run python -m audit_repo_cloner

# Run tests
uv run pytest

# With specific config
uv run python -m audit_repo_cloner --config-file config.1repo.json
```

## Setup

- Requires Python >=3.10 and `uv` for dependency management
- Environment variables: `GITHUB_ACCESS_TOKEN` (required), `GITHUB_ORGANIZATION`, `GITLAB_ACCESS_TOKEN` (optional), `GITLAB_HOSTS` (optional)
- Optionally use `.env` file (see `.env.example`) but environment variables are preferred
- Config file examples: `config.1repo.json.example`, `config.2repo.json.example`, `config.gitlab.json.example`, `config.mixed.json.example`
- `AUDITS_DIR` (optional, default `~/cyfrin/audits`) - local dir where the `report` branch is checked out after cloning
- Config needs `teamName`, `projectName`, `teamWebsite`, `startDate`, `endDate`, `auditors`, `repositories` and a scope markdown file (`scopeFile`, default `scope.md`); repo name and project board title are derived (see `audit_config.py`)

## Architecture

The main workflow lives in `create_audit_repo.py` and runs sequentially:
1. `create_target_repo()` - Creates private GitHub repo via PyGithub API
2. `initialize_repo()` - git init, README, initial push (returns actual branch name since GitHub may use `master` instead of `main`)
3. `clone_source_repo_as_subtree()` - Clones each source repo as a git subtree
4. `remove_source_ci()` - Strips GitHub Actions and GitLab CI files for security
5. `merge_submodules()` - Consolidates .gitmodules from all subtrees
6. `replace_labels_in_repo()` - Removes default labels, adds severity/status labels
7. `create_branches_for_auditors()` - Creates `audit/<name>` branches
8. `add_subtree()` - Adds report-generator-template on the `report` branch and fills its source files via `fill_report_source()`
9. `set_up_ci()` / `set_up_project_board()` - Final configuration
10. `grant_repo_access()` - Gives `Cyfrin/auditors` admin on the repo and project board, invites auditors outside that team with write
11. `check_out_report_branch()` - Clones the `report` branch into `AUDITS_DIR`

Before anything is created, the config is validated and auditors are checked against `source/auditors.json` fetched from `Cyfrin/report-generator-template@main` (every auditor needs a `github` username there).

### Key files

| File | Purpose |
|------|---------|
| `create_audit_repo.py` | Main CLI and workflow orchestration (Click) |
| `audit_config.py` | Config parsing/validation and derived names (repo, board title, timeline) |
| `auditors.py` | Auditor validation against report-generator-template's `auditors.json`, repo access |
| `source_utils.py` | Platform detection (GitHub/GitLab), URL auth/sanitization |
| `github_project_utils.py` | GitHub Projects v2 setup via GraphQL |
| `constants.py` | Issue templates, label definitions, severity colors |
| `create_action.py` | GitHub Actions workflow YAML generation |
| `create_secret.py` | GitHub repo secret encryption via NaCl |

## Code style

- Formatter: black (line-length=300)
- Import sorting: isort (line-length=300)
- Pre-commit hooks configured in `.pre-commit-config.yaml`
- Run `pre-commit run --all-files` to check

## Gotchas

- `build_title_text()`/`slugify()` in `audit_config.py` mirror `scripts/helpers.py` in report-generator-template (which names the report artifacts); keep them in sync.
- `MAIN_BRANCH_NAME` is hardcoded to `"main"` but GitHub repos may default to `master`. The `initialize_repo()` function handles this fallback and returns the actual branch name - always use this returned value downstream rather than the constant.
- The tool does heavy shell-out via `subprocess.run()` for git operations. Many calls use `check=False` so failures are logged but don't halt execution.
- GitHub API has a propagation delay after repo creation - there's a 5-second sleep to handle this.
- Source repo CI/CD files are deliberately removed for security (prevents workflows from running in audit repos).
- `github_project_utils.py` uses GraphQL (via `gql`) because GitHub's REST API doesn't support Projects v2.
