# Audit Repository Cloner

This repository contains a Python package to clone a repo and automatically prepare it for [Cyfrin](https://www.cyfrin.io/) audit report generation. 

# What it does

It will take the following steps:
1. Take the `source` repository you want to setup for audit
2. Add an `issue_template` to the repo, so issues can be formatted as audit findings, like:

```
**Description:**
**Impact:**
**Proof of Concept:**
**Recommended Mitigation:**
**[Project]:** 
**Cyfrin:**
```

3. Update labels to label issues based on severity and status
4. Create branches for each of the auditors participating
5. Create a branch for the final report
6. Add the [report-generator-template](https://github.com/ChainAccelOrg/report-generator-template) to the repo to make it easier to compile the report, and add a button in GitHub actions to re-generate the report on-demand
7. Attempt to set up a GitHub project board

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
git clone https://github.com/ChainAccelOrg/audit-repo-cloner
cd audit-repo-cloner
python3 -m venv venv
source venv/bin/activate
pip install -e .
```

You'll know you've installed it right if you can run:

```
audit_repo_cloner --version
```

And get an output like:

```
audit_repo_cloner, version 0.2.0
```

## Getting a github token

To use this, you'll need a [github personal access token](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token). Please view the docs to set one up. 

You can then set it as an environment variable:

```bash
export GITHUB_TOKEN=xxxxxx
```

Or input it via the CLI (see below for an example)

# Example input and output

Input: https://github.com/code-423n4/2023-04-eigenlayer
Output: https://github.com/81k-ltd/2023-04-eigenlayer

# Usage

*Note: $ denotes a command to run in the terminal*


## Help

```
audit_repo_cloner --help
```

## As a single command

```
audit_repo_cloner --source-url https://github.com/PatrickAlphaC/hardhat-smartcontract-lottery-fcc --auditors "81k-ltd blue-frog-man giiioooooooo" --organization chainaccelorg --github-token <YOUR_GITHUB_TOKEN>
```

```
$ audit_repo_cloner 
Hello! This script will clone target repository and prepare it for a Cyfrin audit. Please enter the following details:

1) Source repo url: 
```
Enter: `https://github.com/code-423n4/2023-04-eigenlayer`

```
2) Enter the names of the auditors (separated by spaces):
```
Enter: `"81k-ltd blue-frog-man giiioooooooo"`

```
3) Enter the name of the organization to create the audit repository in:
```

Enter: <YOUR_ORG_NAME>

```

And you'll get a loooong output, but hopefully you'll have a repo ready for audit!