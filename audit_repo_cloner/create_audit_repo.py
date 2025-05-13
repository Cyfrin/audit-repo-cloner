import glob
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

"""
Audit Repository Cloner

This script clones repositories for auditing smart contracts, removing GitHub Actions
and setting up the necessary structure for a Cyfrin audit. It creates a new repository
with branches for auditors, sets up labels, and configures project boards.
"""

# Configure logging - suppress gql logs
log.basicConfig(level=log.INFO)
log.getLogger("gql.transport.requests").setLevel(log.WARNING)

# Constants
CONFIG_FILE = "config.json"

# Branch names
MAIN_BRANCH_NAME = "main"
REPORT_BRANCH_NAME = "report"

# Subtree configuration
SUBTREE_URL = "https://github.com/Cyfrin/report-generator-template.git"
SUBTREE_NAME = "report-generator-template"
SUBTREE_PATH_PREFIX = "cyfrin-report"
GITHUB_WORKFLOW_ACTION_NAME = "generate-report"

# GitHub Actions related paths
GITHUB_ACTIONS_PATHS = [
    ".github/workflows",
    ".github/actions",
    ".github/action",
]


def setup_git_credentials(github_token):
    """Configure Git credential helper to store credentials temporarily"""
    subprocess.run(["git", "config", "--global", "credential.helper", "store"], check=True)

    # Create credentials file for Git
    cred_file = os.path.expanduser("~/.git-credentials")
    with open(cred_file, "a") as f:
        f.write(f"https://{github_token}@github.com\n")

    return cred_file


def cleanup_git_credentials(cred_file, github_token):
    """Clean up Git credentials after use"""
    try:
        if os.path.exists(cred_file):
            with open(cred_file, "r") as f:
                lines = f.readlines()
            with open(cred_file, "w") as f:
                for line in lines:
                    if github_token not in line:
                        f.write(line)
        # Reset credential helper
        subprocess.run(["git", "config", "--global", "--unset", "credential.helper"], check=False)
    except Exception as e:
        print(f"Warning: Could not clean up git credentials: {e}")


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
    return _create_audit_repo(config_file, github_token, organization)


def _create_audit_repo(
    config_file: str = CONFIG_FILE,
    github_token: str = None,
    organization: str = None,
):
    """Core logic for creating and setting up an audit repository.

    This function:
    1. Creates a new GitHub repository in the specified organization
    2. Clones source repositories as subtrees, removing GitHub Actions
    3. Sets up branches for each auditor and a report branch
    4. Configures labels and issue templates
    5. Adds the report generator template
    6. Sets up CI workflows
    7. Creates a project board for tracking audit findings

    Args:
        config_file: Path to the configuration JSON file
        github_token: GitHub API token with repo creation permissions
        organization: GitHub organization name where repo will be created

    Returns:
        bool: True if the repository was successfully created and configured

    Raises:
        click.UsageError: If required config values are missing
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
        repo_path = os.path.join(temp_dir, target_repo_name)

        # Process each repository
        for repo_config in repositories:
            source_url = repo_config.get("sourceUrl")
            commit_hash = repo_config.get("commitHash")
            sub_folder = repo_config.get("subFolder", "")

            if not source_url or not commit_hash:
                log.warning(f"Skipping repository with missing sourceUrl or commitHash: {repo_config}")
                continue

            clone_source_repo_as_subtree(repo, temp_dir, github_token, source_url, commit_hash, sub_folder)

        # Merge all submodules after all subtrees are added
        merge_submodules(repo_path)

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
        repo = set_up_project_board(repo, github_token, organization, target_repo_name, PROJECT_TEMPLATE_ID, project_title)

    print("Done!")
    return True


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
            raise click.UsageError(f"Repository {organization}/{target_repo_name} already exists.")
    except subprocess.CalledProcessError as e:
        # Repository doesn't exist, continue
        pass

    try:
        repo = github_org.create_repo(target_repo_name, private=True)
        print(f"Created repository {target_repo_name}")
        return repo
    except GithubException as e:
        log.error(f"Error creating remote repository: {e}")
        raise click.UsageError(f"Failed to create repository: {e}")


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
git clone --recurse-submodules [repository-url]
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

    # Push the initial commit to set up the repository
    push_process = subprocess.run(["git", "push", "-u", "origin", current_branch], cwd=repo_path, check=False, capture_output=True, text=True)

    if push_process.returncode != 0:
        log.warning(f"Failed to push initial commit: {push_process.stderr}")
        log.info("Continuing anyway...")


def merge_submodules(repo_path: str):
    """Merge all .gitmodules from subtrees into the root .gitmodules file"""
    root_gitmodules = os.path.join(repo_path, ".gitmodules")
    root_config = {}

    # Find all .gitmodules files using glob and sort them (root first)
    gitmodules_files = glob.glob(os.path.join(repo_path, "**", ".gitmodules"), recursive=True)
    gitmodules_files.sort(key=lambda x: len(os.path.dirname(x)))  # Root will be first as it's shortest path

    if not gitmodules_files:
        log.info("No .gitmodules files found")
        return

    log.info(f"Found {len(gitmodules_files)} .gitmodules files")

    # Process each .gitmodules file
    for gitmodules_file in gitmodules_files:
        try:
            # Get git config
            result = subprocess.run(["git", "config", "-f", gitmodules_file, "--list"], capture_output=True, text=True, check=True)

            # Get relative path from repo root to the .gitmodules directory
            subtree_path = os.path.dirname(os.path.relpath(gitmodules_file, repo_path))

            # First pass: collect all submodule names and their configs
            submodule_configs = {}
            for line in result.stdout.splitlines():
                if not line or "=" not in line:
                    continue

                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Verify this is a submodule config line
                if not key.startswith("submodule."):
                    continue

                # Split into parts and verify structure
                parts = key.split(".")
                if len(parts) < 3:
                    continue

                submodule_name = parts[1]
                config_key = ".".join(parts[2:])

                if submodule_name not in submodule_configs:
                    submodule_configs[submodule_name] = {}
                submodule_configs[submodule_name][config_key] = value

            # Second pass: process and add configs
            for submodule_name, configs in submodule_configs.items():
                if "path" not in configs:
                    continue

                # Determine final name and path
                if gitmodules_file == root_gitmodules:
                    unique_name = submodule_name
                    new_path = configs["path"].replace("\\", "/")
                else:
                    unique_name = f"{subtree_path.replace('/', '_')}_{submodule_name}"
                    new_path = os.path.join(subtree_path, configs["path"]).replace("\\", "/")

                # Add all configs for this submodule
                for config_key, value in configs.items():
                    full_key = f"submodule.{unique_name}.{config_key}"
                    root_config[full_key] = value if config_key != "path" else new_path

        except Exception as e:
            log.warning(f"Error processing .gitmodules from {gitmodules_file}: {str(e)}")
            continue

    # Write combined configuration back to root .gitmodules
    if root_config:
        # First remove existing file to start fresh
        if os.path.exists(root_gitmodules):
            os.remove(root_gitmodules)

        # Write each config
        for key, value in root_config.items():
            try:
                subprocess.run(["git", "config", "-f", root_gitmodules, key, value], check=True, capture_output=True, text=True)
            except subprocess.CalledProcessError as e:
                log.error(f"Failed to write config {key}: {e.stderr}")
                continue

        # Add and commit the changes
        try:
            subprocess.run(["git", "-C", repo_path, "add", ".gitmodules"], check=True)
            subprocess.run(["git", "-C", repo_path, "commit", "-m", "Update .gitmodules with all submodules"], check=True)
            subprocess.run(["git", "-C", repo_path, "push", "origin", MAIN_BRANCH_NAME], check=True)
            log.info("Updated .gitmodules with all submodules")
        except subprocess.CalledProcessError as e:
            log.error(f"Failed to commit/push changes: {e}")
    else:
        log.warning("No submodule configurations found to write")


def verify_files_exist(repo_path, target_dir):
    """
    Verify that files were properly added to the target directory
    Returns True if at least one non-hidden file is found in the target directory
    """
    target_path = os.path.join(repo_path, target_dir)

    if not os.path.exists(target_path):
        raise Exception(f"Target directory {target_dir} does not exist")

    # Walk through the directory and its subdirectories
    for root, dirs, files in os.walk(target_path):
        # Skip hidden directories like .git, .github
        dirs[:] = [d for d in dirs if not d.startswith(".")]

        # Check if we have any non-hidden files
        non_hidden_files = [f for f in files if not f.startswith(".")]
        if non_hidden_files:
            return True

    raise Exception(f"No files found in target directory {target_dir}")


def remove_github_actions(directory_path: str):
    """Remove GitHub Actions directories from cloned repositories for security.

    This prevents any potential security breaches from executing actions
    from the original repositories.
    """
    log.info(f"Removing GitHub Actions from {directory_path}")

    # Use glob to find all matching directories recursively
    for actions_path in GITHUB_ACTIONS_PATHS:
        # Create a pattern to match both the root directory and all subdirectories
        pattern = os.path.join(directory_path, "**", actions_path)

        # Find all matching directories
        for full_path in glob.glob(pattern, recursive=True):
            if os.path.exists(full_path):
                log.info(f"Removing GitHub Actions directory: {full_path}")
                try:
                    # Use shutil.rmtree which works consistently across platforms
                    shutil.rmtree(full_path)
                except Exception as e:
                    log.error(f"Error removing GitHub Actions directory {full_path}: {e}")


def prepare_authenticated_url(source_url: str, github_token: str) -> str:
    """Clean and authenticate a GitHub URL."""
    # Clean source URL
    url = source_url.replace(".git", "")  # remove .git from the url
    url = url.rstrip("/")  # remove any trailing forward slashes

    # Remove /tree/{branch} from URLs - this is a common error when copying from GitHub UI
    url = re.sub(r"/tree/[^/]+/?$", "", url)

    # Add authentication token to the URL for private repositories
    return url.replace("https://", f"https://{github_token}@")


def clone_source_repo_as_subtree(repo: Repository, temp_dir: str, github_token: str, source_url: str, commit_hash: str, sub_folder: str):
    """Clone a source repository and merge it into the target repo using git subtree"""
    repo_path = os.path.join(temp_dir, repo.name)

    # Process and authenticate the URL
    clean_url = prepare_authenticated_url(source_url, github_token)

    url_parts = source_url.split("/")
    source_repo_name = url_parts[-1]

    # Get the target path for the subtree
    subtree_target = sub_folder or source_repo_name
    subtree_path = os.path.join(repo_path, subtree_target)

    # Always forcefully remove the directory if it exists
    if os.path.exists(subtree_path):
        log.info(f"Removing existing directory {subtree_target}")
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

    log.info(f"Adding {source_repo_name} as subtree in {sub_folder or 'root directory'}")

    # Normalize subtree_target for git commands (use forward slashes)
    git_subtree_target = subtree_target.replace("\\", "/")

    # First, configure Git credential helper to store credentials temporarily
    cred_file = setup_git_credentials(github_token)

    try:
        # First pull latest changes from the source repo to ensure it's accessible
        log.info(f"Testing connection to source repository")
        ls_remote_cmd = ["git", "ls-remote", clean_url]
        ls_remote_result = subprocess.run(ls_remote_cmd, cwd=repo_path, capture_output=True, text=True, check=False)

        if ls_remote_result.returncode != 0:
            log.error(f"Could not access repository at {source_url}")
            raise Exception(f"Failed to access repository: {ls_remote_result.stderr}")

        # First add the remote repository
        remote_name = f"subtree_source_{source_repo_name}"

        # Remove the remote if it already exists (to avoid conflicts)
        subprocess.run(["git", "remote", "remove", remote_name], cwd=repo_path, check=False, capture_output=True)

        # Add the remote
        log.info(f"Adding remote repository as '{remote_name}'")
        subprocess.run(["git", "remote", "add", remote_name, clean_url], cwd=repo_path, check=True)

        # Fetch all objects from the remote with tags to ensure we have the commit
        log.info(f"Fetching remote repository data")
        subprocess.run(["git", "fetch", remote_name, "--tags"], cwd=repo_path, check=True)

        # Verify the commit exists
        verify_cmd = ["git", "cat-file", "-t", commit_hash]
        verify_result = subprocess.run(verify_cmd, cwd=repo_path, capture_output=True, text=True, check=False)

        if verify_result.returncode != 0:
            log.info(f"Fetching specific commit {commit_hash}")
            subprocess.run(["git", "fetch", remote_name, commit_hash], cwd=repo_path, check=False)

        # Add the subtree - using --squash to avoid importing entire history
        log.info(f"Adding subtree with prefix {git_subtree_target}")
        subtree_cmd = ["git", "subtree", "add", "--prefix", git_subtree_target, "--squash", remote_name, commit_hash]

        subtree_result = subprocess.run(subtree_cmd, cwd=repo_path, check=False, capture_output=True, text=True)

        if subtree_result.returncode != 0:
            log.error(f"Subtree command failed: {subtree_result.stderr}")
            raise Exception(f"Failed to add subtree: {subtree_result.stderr}")

        # Verify files were actually added
        verify_files_exist(repo_path, git_subtree_target)
        log.info("Subtree added successfully")

    except Exception as e:
        log.error(f"Error in subtree command: {e}")
        raise Exception(f"Failed to add subtree: {e}")
    finally:
        # Clean up credentials
        cleanup_git_credentials(cred_file, github_token)

    # Remove GitHub Actions from the cloned repository for security
    remove_github_actions(subtree_path)

    # Update parent repo
    subprocess.run(["git", "add", "."], cwd=repo_path, check=False)
    subprocess.run(["git", "commit", "-m", f"Add {source_repo_name} at commit {commit_hash[:8]}"], cwd=repo_path, check=False)
    push_process = subprocess.run(["git", "push", "origin", MAIN_BRANCH_NAME], cwd=repo_path, check=False, capture_output=True, text=True)

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
        log.info(f"Created tag {tag_name}")
    except GithubException as e:
        log.error(f"Error creating tag {tag_name}: {e}")


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
        log.info(f"Adding subtree {SUBTREE_NAME}")

        # Create report branch if it doesn't exist
        check_branch = subprocess.run(f"git -C {repo_path} branch --list {REPORT_BRANCH_NAME}", shell=True, capture_output=True, text=True)

        if REPORT_BRANCH_NAME not in check_branch.stdout:
            log.info(f"Creating {REPORT_BRANCH_NAME} branch")
            subprocess.run(f"git -C {repo_path} checkout {MAIN_BRANCH_NAME}", shell=True, check=False)
            subprocess.run(f"git -C {repo_path} checkout -b {REPORT_BRANCH_NAME}", shell=True, check=False)
        else:
            log.info(f"Using existing {REPORT_BRANCH_NAME} branch")
            subprocess.run(f"git -C {repo_path} checkout {REPORT_BRANCH_NAME}", shell=True, check=False)

        # Add the subtree to the repo
        clean_url = prepare_authenticated_url(SUBTREE_URL, github_token)

        # Normalize subtree path for git commands (use forward slashes)
        git_subtree_path = subtree_path.replace("\\", "/")

        # First, configure Git credential helper to store credentials temporarily
        cred_file = setup_git_credentials(github_token)

        try:
            # First test if the repository is accessible
            log.info("Testing connection to report template repository")
            ls_remote_cmd = ["git", "ls-remote", clean_url]
            ls_remote_result = subprocess.run(ls_remote_cmd, cwd=repo_path, capture_output=True, text=True, check=False)

            if ls_remote_result.returncode != 0:
                log.error(f"Could not access repository at {SUBTREE_URL}")
                raise Exception(f"Failed to access repository: {ls_remote_result.stderr}")

            # First add the remote repository
            remote_name = f"subtree_source_{SUBTREE_NAME}"

            # Remove the remote if it already exists (to avoid conflicts)
            subprocess.run(["git", "remote", "remove", remote_name], cwd=repo_path, check=False, capture_output=True)

            # Add the remote
            log.info(f"Adding remote repository as '{remote_name}'")
            subprocess.run(["git", "remote", "add", remote_name, clean_url], cwd=repo_path, check=True)

            # Fetch all objects from the remote with tags to ensure we have the commit
            log.info("Fetching remote repository data")
            subprocess.run(["git", "fetch", remote_name, "--tags"], cwd=repo_path, check=True)

            # Add the subtree - using --squash to avoid importing entire history
            log.info(f"Adding subtree with prefix {git_subtree_path}")
            subtree_cmd = ["git", "subtree", "add", "--prefix", git_subtree_path, "--squash", remote_name, MAIN_BRANCH_NAME]

            subtree_result = subprocess.run(subtree_cmd, cwd=repo_path, check=False, capture_output=True, text=True)

            if subtree_result.returncode != 0:
                log.error(f"Subtree command failed: {subtree_result.stderr}")
                raise Exception(f"Failed to add subtree: {subtree_result.stderr}")

            # Verify files were actually added
            verify_files_exist(repo_path, git_subtree_path)
            log.info("Subtree added successfully")

        except Exception as e:
            log.error(f"Error in subtree command: {e}")
            raise Exception(f"Failed to add subtree: {e}")

        finally:
            # Clean up credentials
            cleanup_git_credentials(cred_file, github_token)

        # Move workflow file to the correct location
        os.makedirs(f"{repo_path}/.github/workflows", exist_ok=True)
        try:
            source = os.path.join(repo_path, git_subtree_path, ".github", "workflows", "main.yml")
            destination = os.path.join(repo_path, ".github", "workflows", "main.yml")

            if os.path.exists(source):
                shutil.move(source, destination)
            else:
                log.warning(f"Workflow file not found at {source}")
        except Exception as e:
            log.warning(f"Error moving workflow file: {e}")

        # Update summary_information.conf
        summary_path = f"{repo_path}/{git_subtree_path}/source/summary_information.conf"
        if os.path.exists(summary_path):
            with open(summary_path, "r") as f:
                summary_information = f.read()

            # Update repository information for all repositories
            for i, repo_info in enumerate(repositories[:3], start=1):  # Max 3 repositories
                suffix = "" if i == 1 else f"_{i}"
                summary_information = re.sub(
                    rf"^project_github{suffix}\s*=.*$",
                    f"project_github{suffix} = {repo_info['sourceUrl']}",
                    summary_information,
                    flags=re.MULTILINE,
                )
                summary_information = re.sub(
                    rf"^commit_hash{suffix}\s*=.*$",
                    f"commit_hash{suffix} = {repo_info['commitHash']}",
                    summary_information,
                    flags=re.MULTILINE,
                )

            summary_information = re.sub(
                r"^private_github\s*=.*$",
                f"private_github = https://github.com/{organization}/{target_repo_name}.git",
                summary_information,
                flags=re.MULTILINE,
            )

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
            log.info(f"The subtree {SUBTREE_NAME} has been added to {repo.name} on branch {REPORT_BRANCH_NAME}")

    except Exception as e:
        log.error(f"Error adding subtree: {e}")
        log.warning("Report generation setup failed, but the repository has been created.")

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
                raise click.UsageError(f"Failed to create branch {branch_name}: {e}")
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
            raise click.UsageError(f"Failed to create report branch: {e}")
    return repo


# IMPORTANT: project creation via REST API is not supported anymore
# https://stackoverflow.com/questions/73268885/unable-to-create-project-in-repository-or-organisation-using-github-rest-api
# we use a non-standard way to access GitHub's GraphQL
def set_up_project_board(repo: Repository, github_token: str, organization: str, target_repo_name: str, project_template_id: str, project_title: str = "DEFAULT PROJECT") -> Repository:
    """Set up a GitHub project board for tracking audit findings.

    Args:
        repo: The GitHub repository object
        github_token: GitHub API token
        organization: GitHub organization name
        target_repo_name: Name of the target repository
        project_template_id: ID of the project template to clone
        project_title: Title for the new project board

    Returns:
        Repository: The GitHub repository object
    """
    if not project_title:
        project_title = "DEFAULT PROJECT"
    try:
        clone_project(repo, github_token, organization, target_repo_name, project_template_id, project_title)
        print("Project board has been set up successfully!")
    except Exception as e:
        print(f"Error occurred while setting up project board: {str(e)}")
        print("Please set up project board manually.")
    return repo


if __name__ == "__main__":
    create_audit_repo()
