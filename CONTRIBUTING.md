# Development Setup

1. Clone and set up the repository:
```bash
git clone https://github.com/Cyfrin/audit-repo-cloner
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
pip install -e .
```

# Code Quality

This project uses pre-commit to ensure code quality. After installing the requirements:

1. Install pre-commit hooks:
```bash
pre-commit install
```

2. Run pre-commit on all files (recommended for initial setup):
```bash
pre-commit run --all-files
```

Note: By default, `pre-commit run` without `--all-files` only checks staged files. If you see "no files to check", either:
1. Stage your files with `git add .` before running pre-commit, or
2. Use `pre-commit run --all-files` to check all files regardless of staging status

# Security Considerations

When contributing to this project, please keep these security considerations in mind:

1. **GitHub Actions Removal**: The tool deliberately removes GitHub Actions from cloned repositories before committing them. This is an important security feature to prevent potential security breaches from executing unknown workflows. Always maintain this functionality.

2. **Credential Handling**: Be careful with how GitHub tokens and other credentials are handled. Never hardcode or log sensitive information.

3. **External Command Execution**: The tool runs many external Git commands. Always sanitize user input and repository paths when constructing these commands.

# Making Changes

1. Create a new branch for your changes:
```bash
git checkout -b your-feature-branch
```

2. Make your changes and commit them:
```bash
git add .
git commit -m "Description of your changes"
```

3. Push your changes and create a pull request:
```bash
git push origin your-feature-branch
```
