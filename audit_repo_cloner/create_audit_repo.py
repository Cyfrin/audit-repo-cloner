import json
import logging as log
import os
import re
import shutil
import subprocess
import tempfile
from datetime import date
from typing import List

import click
from dotenv import load_dotenv
from github import Github, GithubException, Repository

from audit_repo_cloner.__version__ import __title__, __version__
from audit_repo_cloner.constants import DEFAULT_LABELS, ISSUE_TEMPLATE, PROJECT_TEMPLATE_ID, SEVERITY_DATA
from audit_repo_cloner.create_action import create_action
from audit_repo_cloner.github_project_utils import clone_project

# Configure logging - suppress gql logs
log.basicConfig(level=log.INFO)
log.getLogger("gql.transport.requests").setLevel(log.WARNING)

# Globals are shit. We should refactor again in the future...
REPORT_BRANCH_NAME = "report"
MAIN_BRANCH_NAME = "main"
SUBTREE_URL = "https://github.com/Cyfrin/report-generator-template.git"
SUBTREE_NAME = "report-generator-template"
SUBTREE_PATH_PREFIX = "cyfrin-report"
GITHUB_WORKFLOW_ACTION_NAME = "generate-report"
CONFIG_FILE = "config.json"


@click.command()
@click.version_option(
    version=__version__,
    prog_name=__title__,
)
@click.option("--config-file", help="Path to config.json file.", default=CONFIG_FILE)
@click.option("--github-token", help="Your GitHub developer token to make API calls.", default=os.getenv("GITHUB_ACCESS_TOKEN"))
@click.option("--organization", help="Your GitHub organization name in which to clone the repo.", default=os.getenv("GITHUB_ORGANIZATION"))
def create_audit_repo(
    config_file: str = CONFIG_FILE,
    github_token: str = None,
    organization: str = None,
):
    """This function clones multiple repositories and prepares them for a Cyfrin audit using the provided configuration.

    Args:
        config_file (str): Path to the configuration file containing repository details.
        github_token (str): The GitHub developer token to make API calls.
        organization (str): The GitHub organization to create the audit repository in.

    Returns:
        None
    """

    if not os.path.exists(config_file):
        raise click.UsageError(f"Config file {config_file} not found. Please create one based on config.json.example.")

    with open(config_file, "r") as f:
        config = json.load(f)

    # Extract config values
    target_repo_name = config.get("targetRepoName")
    project_title = config.get("projectTitle")
    auditors = config.get("auditors")
    repositories = config.get("repositories", [])

    if not repositories:
        raise click.UsageError("No repositories specified in the config file.")

    if not target_repo_name or not auditors:
        raise click.UsageError("Target repo name and auditors must be provided in the config file.")

    github_token, organization = prompt_for_token_and_org(github_token, organization)
    if not github_token or not organization:
        raise click.UsageError("GitHub token and organization must be provided either through environment variables or as options.")

    auditors_list: List[str] = [a.strip() for a in auditors.split(" ")]
    subtree_path = f"{SUBTREE_PATH_PREFIX}/{SUBTREE_NAME}"

    with tempfile.TemporaryDirectory() as temp_dir:
        # Create the target repo
        repo = create_target_repo(github_token, organization, target_repo_name)

        # Initialize the repo with README
        initialize_repo(repo, temp_dir, github_token, organization, target_repo_name)

        # Process each repository
        for repo_config in repositories:
            source_url = repo_config.get("sourceUrl")
            commit_hash = repo_config.get("commitHash")
            sub_folder = repo_config.get("subFolder", "")

            if not source_url or not commit_hash:
                log.warning(f"Skipping repository with missing sourceUrl or commitHash: {repo_config}")
                continue

            clone_source_repo_as_subtree(repo, temp_dir, github_token, source_url, commit_hash, sub_folder)

        repo = add_issue_template_to_repo(repo)
        repo = replace_labels_in_repo(repo)
        repo = create_branches_for_auditors(repo, auditors_list, repo.get_commits()[0].sha)
        repo = create_report_branch(repo, repo.get_commits()[0].sha)
        repo = add_subtree(
            repo,
            target_repo_name,
            organization,
            temp_dir,
            subtree_path,
            repositories,
            github_token,
        )
        repo = set_up_ci(repo, subtree_path)
        set_up_project_board(repo, github_token, organization, target_repo_name, PROJECT_TEMPLATE_ID, project_title)

    print("Done!")


def create_target_repo(github_token: str, organization: str, target_repo_name: str) -> Repository:
    github_object = Github(github_token)
    github_org = github_object.get_organization(organization)

    try:
        print(f"Checking whether {target_repo_name} already exists...")
        git_command = [
            "git",
            "ls-remote",
            "-h",
            f"https://{github_token}@github.com/{organization}/{target_repo_name}",
        ]

        result = subprocess.run(
            git_command,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        if result.returncode == 0:
            log.error(f"{organization}/{target_repo_name} already exists.")
            exit()
    except subprocess.CalledProcessError as e:
        # Repository doesn't exist, continue
        pass

    try:
        repo = github_org.create_repo(target_repo_name, private=True)
        print(f"Created repository {target_repo_name}")
        return repo
    except GithubException as e:
        log.error(f"Error creating remote repository: {e}")
        exit()


def initialize_repo(repo: Repository, temp_dir: str, github_token: str, organization: str, target_repo_name: str):
    """Initialize the target repository with a README file"""
    repo_path = os.path.join(temp_dir, target_repo_name)
    os.makedirs(repo_path, exist_ok=True)

    # Initialize git repo
    subprocess.run(["git", "init"], cwd=repo_path, check=False)

    # Set the default branch name
    # Git 2.28+ can set init.defaultBranch, but we'll handle both new and old git versions
    subprocess.run(["git", "checkout", "-b", MAIN_BRANCH_NAME], cwd=repo_path, check=False)

    # Create README.md
    with open(os.path.join(repo_path, "README.md"), "w") as f:
        f.write(
            f"""# {target_repo_name}

## Getting Started
Clone the repository:

```bash
git clone [repository-url]
```
The source code for all audit target repositories has been merged into this repository using git subtree, ensuring that all code and history is preserved even if the original repositories are moved or deleted.
            """
        )

    # Configure git
    subprocess.run(["git", "config", "user.name", "Cyfrin Bot"], cwd=repo_path, check=False)
    subprocess.run(["git", "config", "user.email", "bot@cyfrin.io"], cwd=repo_path, check=False)

    # Add remote
    subprocess.run(["git", "remote", "add", "origin", f"https://{github_token}@github.com/{organization}/{target_repo_name}.git"], cwd=repo_path, check=False)

    # Commit and push
    subprocess.run(["git", "add", "."], cwd=repo_path, check=False)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo_path, check=False)

    # Check the current branch
    branch_process = subprocess.run(["git", "branch", "--show-current"], cwd=repo_path, capture_output=True, text=True, check=False)
    current_branch = branch_process.stdout.strip() or MAIN_BRANCH_NAME

    # Push to the current branch
    push_result = subprocess.run(["git", "push", "-u", "origin", current_branch], cwd=repo_path, capture_output=True, text=True, check=False)

    if push_result.returncode != 0:
        log.error(f"Failed to push to {current_branch}: {push_result.stderr}")

        # If failed and current branch is 'main', try 'master' instead
        if current_branch == "main":
            log.info("Attempting to push to 'master' branch instead...")
            subprocess.run(["git", "branch", "-m", "main", "master"], cwd=repo_path, check=False)
            subprocess.run(["git", "push", "-u", "origin", "master"], cwd=repo_path, check=False)


def clone_source_repo_as_subtree(repo: Repository, temp_dir: str, github_token: str, source_url: str, commit_hash: str, sub_folder: str):
    """Clone a source repository and merge it into the target repo using git subtree"""
    repo_path = os.path.join(temp_dir, repo.name)

    # Clean source URL
    source_url = source_url.replace(".git", "")  # remove .git from the url
    source_url = source_url.rstrip("/")  # remove any trailing forward slashes

    # Remove /tree/{branch} from URLs - this is a common error when copying from GitHub UI
    source_url = re.sub(r"/tree/[^/]+/?$", "", source_url)

    # Add authentication token to the URL for private repositories
    authenticated_url = source_url.replace("https://", f"https://{github_token}@")

    url_parts = source_url.split("/")
    url_parts[-2]
    source_repo_name = url_parts[-1]

    # Get the target path for the subtree
    subtree_target = sub_folder or source_repo_name
    subtree_path = os.path.join(repo_path, subtree_target)

    # Always forcefully remove the directory if it exists
    if os.path.exists(subtree_path):
        log.info(f"Removing existing directory {subtree_path}")
        try:
            if os.name == "nt":  # Windows
                subprocess.run(f'rmdir /S /Q "{subtree_path}"', shell=True, check=False)
            else:  # Unix-like
                subprocess.run(f'rm -rf "{subtree_path}"', shell=True, check=False)
        except Exception as e:
            log.error(f"Error removing directory: {e}")
            raise Exception(f"Cannot add subtree: directory {subtree_target} exists and could not be removed")

    # Create subfolder if needed for parent directories
    if sub_folder:
        parent_dir = os.path.dirname(subtree_path)
        os.makedirs(parent_dir, exist_ok=True)

    print(f"Adding {source_repo_name} as subtree in {sub_folder or 'root directory'}...")

    try:
        # Add the subtree to the repo
        subtree_result = subprocess.run(f"git -C {repo_path} subtree add --prefix {subtree_target} {authenticated_url} {commit_hash}", shell=True, check=False, capture_output=True, text=True)

        if subtree_result.returncode != 0:
            raise Exception(f"Failed to add subtree: {subtree_result.stderr}")

        # Update parent repo
        subprocess.run(["git", "add", "."], cwd=repo_path, check=False)
        subprocess.run(["git", "commit", "-m", f"Add {source_repo_name} at commit {commit_hash[:8]}"], cwd=repo_path, check=False)
        push_process = subprocess.run(["git", "push"], cwd=repo_path, check=False, capture_output=True, text=True)

        if push_process.returncode != 0:
            log.warning(f"Failed to push changes: {push_process.stderr}")
            log.info("Continuing anyway...")

        # Create tag in the main repo pointing to this commit
        tag_name = f"{source_repo_name}-cyfrin-audit"
        try:
            tag = repo.create_git_tag(
                tag=tag_name,
                message=f"Cyfrin audit tag for {source_repo_name}",
                object=repo.get_commits()[0].sha,
                type="commit",
            )
            repo.create_git_ref(ref=f"refs/tags/{tag.tag}", sha=tag.sha)
            print(f"Created tag {tag_name}")
        except GithubException as e:
            log.error(f"Error creating tag {tag_name}: {e}")

    except Exception as e:
        log.error(f"Error adding subtree for {source_repo_name}: {e}")
        log.warning("Continuing with the next repository...")


def prompt_for_token_and_org(github_token: str, organization: str):
    """Prompt for GitHub token and organization if not provided"""
    load_dotenv(override=True)
    if not github_token:
        github_token = os.getenv("GITHUB_ACCESS_TOKEN") or input("Enter your Github token: ")
    if not organization:
        organization = os.getenv("GITHUB_ORGANIZATION") or input("Enter the name of the organization to create the audit repository in: ")
    return github_token, organization


def add_subtree(
    repo: Repository,
    target_repo_name: str,
    organization: str,
    repo_path: str,
    subtree_path: str,
    repositories: List[dict],
    github_token: str = None,
):
    # Add report-generator-template as a subtree
    repo_path = os.path.join(repo_path, target_repo_name)

    try:
        print(f"Adding subtree {SUBTREE_NAME}...")

        # Create report branch if it doesn't exist
        check_branch = subprocess.run(f"git -C {repo_path} branch --list {REPORT_BRANCH_NAME}", shell=True, capture_output=True, text=True)

        if REPORT_BRANCH_NAME not in check_branch.stdout:
            print(f"Creating {REPORT_BRANCH_NAME} branch...")
            subprocess.run(f"git -C {repo_path} checkout {MAIN_BRANCH_NAME}", shell=True, check=False)
            subprocess.run(f"git -C {repo_path} checkout -b {REPORT_BRANCH_NAME}", shell=True, check=False)
        else:
            print(f"Branch {REPORT_BRANCH_NAME} already exists, checking it out...")
            subprocess.run(f"git -C {repo_path} checkout {REPORT_BRANCH_NAME}", shell=True, check=False)

        # Add the subtree to the repo
        authenticated_subtree_url = SUBTREE_URL.replace("https://", f"https://{github_token}@")
        subtree_result = subprocess.run(f"git -C {repo_path} subtree add --prefix {subtree_path} {authenticated_subtree_url} {MAIN_BRANCH_NAME} --squash", shell=True, check=False, capture_output=True, text=True)

        if subtree_result.returncode != 0:
            log.error(f"Error adding subtree: {subtree_result.stderr}")
            raise Exception(f"Failed to add subtree: {subtree_result.stderr}")

        # Move workflow file to the correct location
        os.makedirs(f"{repo_path}/.github/workflows", exist_ok=True)
        try:
            source = os.path.join(repo_path, subtree_path, ".github", "workflows", "main.yml")
            destination = os.path.join(repo_path, ".github", "workflows", "main.yml")

            if os.path.exists(source):
                shutil.move(source, destination)
            else:
                log.warning(f"Workflow file not found at {source}")
        except Exception as e:
            log.warning(f"Error moving workflow file: {e}")

        # Update summary_information.conf
        summary_path = f"{repo_path}/{subtree_path}/source/summary_information.conf"
        if os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                summary_information = f.read()

            # Update repository information for all repositories
            for i, repo_info in enumerate(repositories[:3], start=1):  # Max 3 repositories
                suffix = "" if i == 1 else f"_{i}"
                summary_information = re.sub(
                    f"^project_github{suffix} = .*$",
                    f"project_github{suffix} = {repo_info['sourceUrl']}",
                    summary_information,
                    flags=re.MULTILINE,
                )
                summary_information = re.sub(
                    f"^commit_hash{suffix} = .*$",
                    f"commit_hash{suffix} = {repo_info['commitHash']}",
                    summary_information,
                    flags=re.MULTILINE,
                )

            summary_information = re.sub(
                r"^private_github = .*$",
                f"private_github = https://github.com/{organization}/{target_repo_name}.git",
                summary_information,
                flags=re.MULTILINE,
            )

            print(summary_information)

            with open(summary_path, "w") as f:
                f.write(summary_information)
        else:
            log.warning(f"Summary information file not found at {summary_path}")

        # Commit and push changes
        subprocess.run(f"git -C {repo_path} add .", shell=True)
        commit_result = subprocess.run(f'git -C {repo_path} commit -m "install: {SUBTREE_NAME}"', shell=True, check=False, capture_output=True, text=True)

        if commit_result.returncode != 0 and "nothing to commit" not in commit_result.stdout:
            log.warning(f"Error committing changes: {commit_result.stderr}")

        # Always use force push since we want our version to take precedence
        push_result = subprocess.run(f"git -C {repo_path} push --force origin {REPORT_BRANCH_NAME}", shell=True, check=False, capture_output=True, text=True)

        if push_result.returncode != 0:
            log.warning(f"Error force pushing changes: {push_result.stderr}")
            log.warning("You may need to push changes manually.")
        else:
            print(f"The subtree {SUBTREE_NAME} has been added to {repo.name} on branch {REPORT_BRANCH_NAME}")

    except Exception as e:
        log.error(f"Error adding subtree: {e}")
        log.warning("Report generation setup failed, but the repository has been created.")
        return repo

    return repo


def set_up_ci(repo, subtree_path: str):
    try:
        create_action(
            repo,
            GITHUB_WORKFLOW_ACTION_NAME,
            subtree_path,
            REPORT_BRANCH_NAME,
            str(date.today()),
        )
    except Exception as e:
        log.warn(f"Error occurred while setting up CI: {str(e)}")
        log.warn("Please set up CI manually using the report-generation.yml file.")

    return repo


def prompt_for_details(source_url: str, target_repo_name: str, commit_hash: str, auditors: str, github_token: str, organization: str, project_title: str):
    while True:
        prompt_counter = 1

        if not source_url:
            source_url = input(f"Hello! This script will clone the source repository and prepare it for a Cyfrin audit. Please enter the following details:\n\n{prompt_counter}) Source repo url: ")
            prompt_counter += 1
        if not target_repo_name:
            target_repo_name = input(f"\n{prompt_counter}) Target repo name (leave blank to use source repo name): ")
            prompt_counter += 1
        if not commit_hash:
            commit_hash = input(f"\n{prompt_counter}) Audit commit hash (be sure to copy the full SHA): ")
            prompt_counter += 1
        if not auditors:
            auditors = input(f"\n{prompt_counter}) Enter the names of the auditors (separated by spaces): ")
        if not github_token:
            github_token = input(f"\n{prompt_counter}) Enter your Github token: ")
            prompt_counter += 1
        if not organization:
            organization = input(f"\n{prompt_counter}) Enter the name of the organization to create the audit repository in: ")
            prompt_counter += 1
        if not project_title:
            project_title = input(f"\n{prompt_counter}) Enter the title of the GitHub project board: ")
            prompt_counter += 1

        if source_url and commit_hash and auditors and github_token and organization and project_title:
            break
        print("Please fill in all the details.")
    return source_url, target_repo_name, commit_hash, auditors, github_token, organization, project_title


def create_audit_tag(repo, repo_path, commit_hash) -> Repository:
    log.info("Creating audit tag...")

    try:
        tag = repo.create_git_tag(
            tag="cyfrin-audit",
            message="Cyfrin audit tag",
            object=commit_hash,
            type="commit",
        )

        # Now create a reference to this tag in the repository
        repo.create_git_ref(ref=f"refs/tags/{tag.tag}", sha=tag.sha)
    except GithubException as e:
        log.error(f"Error creating audit tag: {e}")
        log.info("Attempting to create tag manually...")

        try:
            # Create the tag at the specific commit hash
            subprocess.run(["git", "-C", repo_path, "tag", "cyfrin-audit", commit_hash])

            # Push the tag to the remote repository
            subprocess.run(["git", "-C", repo_path, "push", "origin", "cyfrin-audit"])
        except GithubException as e:
            log.error(f"Error creating audit tag manually: {e}")
            repo.delete()
            exit()
    return repo


def add_issue_template_to_repo(repo) -> Repository:
    # Get the existing finding.md file, if it exists
    try:
        finding_file = repo.get_contents(".github/ISSUE_TEMPLATE/finding.md")
    except GithubException:
        finding_file = None

    # If finding.md already exists, leave it be. Otherwise, create the file.
    if finding_file is None:
        repo.create_file(".github/ISSUE_TEMPLATE/finding.md", "finding.md", ISSUE_TEMPLATE)
    return repo


def delete_default_labels(repo) -> Repository:
    log.info("Deleting default labels...")
    for label_name in DEFAULT_LABELS:
        try:
            label = repo.get_label(label_name)
            log.info(f"Deleting {label}...")
            label.delete()
        except Exception:
            log.warn(f"Label {label} does not exist. Skipping...")
    log.info("Finished deleting default labels")
    return repo


def create_new_labels(repo) -> Repository:
    log.info("Creating new labels...")
    for data in SEVERITY_DATA:
        try:
            repo.create_label(**data)
        except:
            log.warn(f"Issue creating label with data: {data}. Skipping...")
    print("Finished creating new labels")
    return repo


def create_branches_for_auditors(repo, auditors_list, commit_hash) -> Repository:
    for auditor in auditors_list:
        branch_name = f"audit/{auditor}"
        try:
            repo.create_git_ref(f"refs/heads/{branch_name}", commit_hash)
        except GithubException as e:
            if e.status == 422:
                log.warn(f"Branch {branch_name} already exists. Skipping...")
                continue
            else:
                log.error(f"Error creating branch: {e}")
                repo.delete()
                exit()
    return repo


def replace_labels_in_repo(repo) -> Repository:
    repo = delete_default_labels(repo)
    repo = create_new_labels(repo)
    return repo


def create_report_branch(repo, commit_hash) -> Repository:
    try:
        repo.create_git_ref(ref=f"refs/heads/{REPORT_BRANCH_NAME}", sha=commit_hash)
    except GithubException as e:
        if e.status == 422:
            log.warn(f"Branch {REPORT_BRANCH_NAME} already exists. Skipping...")
        else:
            log.error(f"Error creating branch: {e}")
            repo.delete()
            exit()
    return repo


# IMPORTANT: project creation via REST API is not supported anymore
# https://stackoverflow.com/questions/73268885/unable-to-create-project-in-repository-or-organisation-using-github-rest-api
# we use a non-standard way to access GitHub's GraphQL
def set_up_project_board(repo: Repository, github_token: str, organization: str, target_repo_name: str, project_template_id: str, project_title: str = "DEFAULT PROJECT"):
    if not project_title:
        project_title = "DEFAULT PROJECT"
    try:
        clone_project(repo, github_token, organization, target_repo_name, project_template_id, project_title)
        print("Project board has been set up successfully!")
    except Exception as e:
        print(f"Error occurred while setting up project board: {str(e)}")
        print("Please set up project board manually.")
    return


if __name__ == "__main__":
    create_audit_repo()
