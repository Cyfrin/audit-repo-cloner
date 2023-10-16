# Audit Repository Cloner

This repository contains a Python package to clone a repo and automatically prepare it for [Cyfrin](https://www.cyfrin.io/) audit report generation. 

# What it does

It will take the following steps:
1. Take the `source` repository you want to set up for audit
2. Take the `target` repository name you want to use for the private --repo
3. Add an `issue_template` to the repo, so issues can be formatted as audit findings, like:

```
**Description:**
**Impact:**
**Proof of Concept:**
**Recommended Mitigation:**
**[Project]:** 
**Cyfrin:**
```

3. Update labels to label issues based on severity and status
4. Create an audit tag at the given commit hash (full SHA)
5. Create branches for each of the auditors participating
6. Create a branch for the final report
7. Add the [report-generator-template](https://github.com/Cyfrin/report-generator-template) to the repo to make it easier to compile the report, and add a button in GitHub actions to re-generate the report on-demand
8. Attempt to set up a GitHub project board

Note: Changes to `report-generator-template` can be pulled into the generated repo by running:
```bash
git subtree pull --prefix cyfrin-report/report-generator-template https://github.com/Cyfrin/report-generator-template main --squash
```

# Getting Started

## Requirements

- [git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git)
  - You'll know you did it right if you can run `git --version` and you see a response like `git version x.x.x`
- [Python](https://www.python.org/downloads/)
  - You'll know you've installed python right if you can run:
    - `python --version` or `python3 --version` and get an ouput like: `Python x.x.x`
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

```
audit_repo_cloner --version
```

And get an output like:

```
audit_repo_cloner, version 0.2.2
```

## Getting a GitHub token

To use this, you'll need a [github personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token). Please view the docs to set one up. 

You can then set it as an environment variable or input it via the CLI:

```bash
export ACCESS_TOKEN=xxxxxx
```

Note: this access token is only used to create the repo initially. To allow the GitHub Action to run the report generator (fetching issues) in CI, be sure to set appropriate permissions for the global [`GITHUB_TOKEN` secret](https://docs.github.com/en/actions/security-guides/automatic-token-authentication).

# Usage

*Note: $ denotes a command to run in the terminal*


## Help

```
audit_repo_cloner --help
```

## As a single command

From source:
```bash
python ./create_audit_repo.py`
```

Otherwise (pipx):

```
audit_repo_cloner --source-url https://github.com/PatrickAlphaC/hardhat-smartcontract-lottery-fcc --target-repo-name "" --commit-hash 5e4872358cd2bda1936c29f460ece2308af4def6 --auditors "tricky-p blue-frog-man giiioooooooo" --organization cyfrin --github-token <YOUR_ACCESS_TOKEN>
```

```
$ audit_repo_cloner 
"Hello! This script will clone the source repository and prepare it for a Cyfrin audit. Please enter the following details:

1) Source repo url: 
```
Enter: `https://github.com/Cyfrin/foundry-full-course-f23`

```
2) Target repo name (leave blank to use source repo name):
```
Enter: `""`

```
3) Audit commit hash: 
```
Enter: `25d62b685857f5c1906675a3876d7d7773a8b3bd`

```
4) Enter the names of the auditors (separated by spaces):
```
Enter: `"tricky-p blue-frog-man giiioooooooo"`

```
5) Enter the name of the organization to create the audit repository in:
```

Enter: `<YOUR_ORG_NAME>`

And you'll get a loooong output, but, hopefully, you'll have a repo ready for audit!
