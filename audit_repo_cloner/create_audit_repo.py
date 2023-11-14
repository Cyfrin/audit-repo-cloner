import os
from datetime import date
from typing import List, Optional, Tuple
from github import Github, GithubException, Repository, Organization
from dotenv import load_dotenv
from .create_action import create_action
import click
import subprocess
import tempfile
import logging as log
import yaml
import re
from .__version__ import __version__, __title__

from .constants import (
    ISSUE_TEMPLATE,
    DEFAULT_LABELS,
    SEVERITY_DATA,
    TRELLO_LABELS,
    TRELLO_COLUMNS,
)

log.basicConfig(level=log.INFO)

load_dotenv()

# Globals are shit. We should refactor again in the future...
REPORT_BRANCH_NAME = "report"
MAIN_BRANCH_NAME = "main"
SUBTREE_URL = "https://github.com/Cyfrin/report-generator-template.git"
SUBTREE_NAME = "report-generator-template"
SUBTREE_PATH_PREFIX = "cyfrin-report"
GITHUB_WORKFLOW_ACTION_NAME = "generate-report"


@click.command()
@click.version_option(
    version=__version__,
    prog_name=__title__,
)
@click.option("--config", type=click.Path(exists=True), help="Path to YAML config file")
@click.option("--prompt/--no-prompt", help="Have this CLI be interactive by prompting or pass in args via the command.")
@click.option("--source-url", help="Source repository URL.")
@click.option("--target-repo-name", help="Target repository name (leave blank to use source repo name).")
@click.option("--commit-hash", help="Audit commit hash.")
@click.option("--auditors", help="Names of the auditors (separated by spaces).")
@click.option("--github-token",help="Your GitHub developer token to make API calls.")
@click.option("--organization",help="Your GitHub organization name in which to clone the repo.")
def create_audit_repo(
    config: str = "",
    prompt: bool = True,
    source_url: str = None,
    target_repo_name: str = None,
    commit_hash: str = None,
    auditors: str = None,
    github_token: str = os.getenv("ACCESS_TOKEN"),
    organization: str =os.getenv("GITHUB_ORGANIZATION"),
):
    """This function clones a target repository and prepares it for a Cyfrin audit using the provided arguments.
    If the prompt flag is set to true (default), the user will be prompted for the source repository URL and auditor names.
    If the prompt flag is set to false, the function will use the provided click arguments for the source repository URL and auditor names.

    Args:
        prompt (bool): Determines if the script should use default prompts for input or the provided click arguments.
        source_url (str): The URL of the source repository to be cloned and prepared for the Cyfrin audit.
        target_repo_name (str): The name of the target repository to be created.
        auditors (str): A space-separated list of auditor names who will be assigned to the audit.
        github_token (str): The GitHub developer token to make API calls.
        organization (str): The GitHub organization to create the audit repository in.

    Returns:
        None
    """
    if config:
        (
            source_url,
            target_repo_name,
            auditors,
            github_token,
            organization,
        ) = load_config(
            config,
            source_url=source_url,
            target_repo_name=target_repo_name,
            auditors=auditors,
            github_token=github_token,
            organization=organization,
        )
    if prompt:
        (
            source_url,
            target_repo_name,
            commit_hash,
            auditors,
            organization,
        ) = prompt_for_details(
            source_url, target_repo_name, commit_hash, auditors, organization
        )
    if not source_url or not commit_hash or not auditors or not organization:
        raise click.UsageError(
            "Source URL, commit hash, organization, and auditors must be provided either through --prompt, config, or as options."
        )
    if not github_token:
        raise click.UsageError(
            "GitHub token must be provided either through config or environment variable."
        )

    source_url = source_url.replace(".git", "")  # remove .git from the url
    url_parts = source_url.split("/")
    source_username = url_parts[-2]
    source_repo_name = url_parts[-1]
    auditors_list: List[str] = [a.strip() for a in auditors.split(" ")]
    subtree_path = f"{SUBTREE_PATH_PREFIX}/{SUBTREE_NAME}"

    # if target_repo_name is not provided, attempt to use the source repo name
    if not target_repo_name:
        target_repo_name = source_repo_name

    with tempfile.TemporaryDirectory() as temp_dir:
        repo = try_clone_repo(
            github_token,
            organization,
            target_repo_name,
            source_repo_name,
            source_username,
            temp_dir,
            commit_hash,
        )

        repo = create_audit_tag(repo, temp_dir, commit_hash)
        repo = add_issue_template_to_repo(repo)
        repo = replace_labels_in_repo(repo)
        repo = create_branches_for_auditors(repo, auditors_list, commit_hash)
        repo = create_report_branch(repo, commit_hash)
        repo = add_subtree(
            repo,
            source_repo_name,
            target_repo_name,
            source_username,
            organization,
            temp_dir,
            subtree_path,
            commit_hash,
        )
        repo = set_up_ci(repo, subtree_path)
        repo = set_up_project_board(repo, source_username, target_repo_name)

    print("Done!")


def add_subtree(
    repo: Repository,
    source_repo_name: str,
    target_repo_name: str,
    source_username: str,
    organization: str,
    repo_path: str,
    subtree_path: str,
    commit_hash: str,
):
    # Add report-generator-template as a subtree

    try:
        print(f"Adding subtree {SUBTREE_NAME}...")

        # Pull the latest changes from the origin
        subprocess.run(
            f"git -C {repo_path} pull origin {REPORT_BRANCH_NAME} --rebase", shell=True, check=False
        )
        subprocess.run(f"git -C {repo_path} checkout {REPORT_BRANCH_NAME}", shell=True, check=False)

        # Add the subtree to the repo
        subprocess.run(
            f"git -C {repo_path} subtree add --prefix {subtree_path} {SUBTREE_URL} {MAIN_BRANCH_NAME} --squash",
            shell=True, check=False
        )
        os.makedirs(f"{repo_path}/.github/workflows", exist_ok=True)
        subprocess.run(
            f"mv {repo_path}/{subtree_path}/.github/workflows/main.yml {repo_path}/.github/workflows/main.yml",
            shell=True, check=False
        )

        with open(
            f"{repo_path}/{subtree_path}/source/summary_information.conf", "r"
        ) as f:
            summary_information = f.read()

            summary_information = re.sub(
                r"^project_github = .*$",
                f"project_github = https://github.com/{source_username}/{source_repo_name}.git",
                summary_information,
                flags=re.MULTILINE,
            )

            summary_information = re.sub(
                r"^private_github = .*$",
                f"private_github = https://github.com/{organization}/{target_repo_name}.git",
                summary_information,
                flags=re.MULTILINE,
            )

            summary_information = re.sub(
                r"^commit_hash = .*$",
                f"commit_hash = {commit_hash}",
                summary_information,
                flags=re.MULTILINE,
            )

            with open(
                f"{repo_path}/{subtree_path}/source/summary_information.conf", "w"
            ) as f:
                f.write(summary_information)

        subprocess.run(f"git -C {repo_path} add .", shell=True)
        subprocess.run(
            f"git -C {repo_path}  commit -m 'install: {SUBTREE_NAME}'", shell=True, check=False
        )

        # Push the changes back to the origin
        subprocess.run(
            f"git -C {repo_path} push origin {REPORT_BRANCH_NAME}", shell=True, check=False
        )

        print(
            f"The subtree {SUBTREE_NAME} has been added to {repo.name} on branch {REPORT_BRANCH_NAME}"
        )

    except GithubException as e:
        log.error(f"Error adding subtree: {e}")
        repo.delete()
        exit()

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


def set_up_project_board(repo, source_username: str, target_repo_name: str):
    try:
        repo.edit(has_projects=True)
        project = repo.create_project(
            f"{source_username}/{target_repo_name}",
            body=f"A collaborative board for the {source_username}/{target_repo_name} audit",
        )
        columns = [project.create_column(name) for name in TRELLO_COLUMNS]
        project.create_custom_field(
            name="Status", type="dropdown", possible_values=TRELLO_LABELS
        )
        project.create_custom_field(name="PoC", type="boolean")

        # Define the column-to-label mapping
        column_to_label_mapping = {
            column: label for column, label in zip(columns, TRELLO_LABELS)
        }

        # Define the workflow action
        def handle_card_move(event):
            card = event.project_card
            column = card.column
            label = column_to_label_mapping.get(column)
            if label:
                issue = card.get_content()
                issue.add_to_labels(label)

        # Register the workflow
        project.add_to_event_handlers("project_card_move", handle_card_move)
        print("Project board has been set up successfully!")
    except Exception as e:
        print(f"Error occurred while setting up project board: {str(e)}")
        print("Please set up project board manually.")

    return repo


def load_config(
    config: str,
    source_url: Optional[str] = None,
    target_repo_name: Optional[str] = None,
    auditors: Optional[str] = None,
    github_token: Optional[str] = None,
    organization: Optional[str] = None,
) -> Tuple[str, str, str, str]:
    """Loads the configuration file and returns the values.

    Args:
        config (str): The path to the configuration file.
        source_url (Optional[str], optional): The URL you want to download. Defaults to None.
        target_repo_name (Optional[str], optional): The name of the target repository. Defaults to None.
        auditors (Optional[str], optional): The list of auditors separated by spaces. Defaults to None.
        github_token (Optional[str], optional): The GitHub token to use. Defaults to None.
        organization (Optional[str], optional): The organization to make the github repo. Defaults to None.

    Returns:
        Tuple[str, str, str, str]: The source URL, auditors, GitHub token, and organization.
    """
    with open(config, "r") as f:
        config_data = yaml.safe_load(f)
        source_url = (
            config_data.get("source_url", source_url)
            if source_url is None
            else source_url
        )

        target_repo_name = (
            config_data.get("target_repo_name", target_repo_name)
            if target_repo_name is None
            else target_repo_name
        )

        auditors = (
            config_data.get("auditors", auditors) if auditors is None else auditors
        )
        github_token = (
            config_data.get("github_token", github_token)
            if github_token is None
            else github_token
        )
        organization = (
            config_data.get("organization", organization)
            if organization is None
            else organization
        )
    return source_url, target_repo_name, auditors, github_token, organization


def prompt_for_details(
    source_url: str,
    target_repo_name: str,
    commit_hash: str,
    auditors: str,
    organization: str,
):
    while True:
        prompt_counter = 1

        if not source_url:
            source_url = input(
                f"Hello! This script will clone the source repository and prepare it for a Cyfrin audit. Please enter the following details:\n\n{prompt_counter}) Source repo url: "
            )
            prompt_counter += 1
        if not target_repo_name:
            target_repo_name = input(
                f"\n{prompt_counter}) Target repo name (leave blank to use source repo name): "
            )
            prompt_counter += 1
        if not commit_hash:
            commit_hash = input(
                f"\n{prompt_counter}) Audit commit hash (be sure to copy the full SHA): "
            )
            prompt_counter += 1
        if not auditors:
            auditors = input(
                f"\n{prompt_counter}) Enter the names of the auditors (separated by spaces): "
            )
            prompt_counter += 1
        if not organization:
            organization = input(
                f"\n{prompt_counter}) Enter the name of the organization to create the audit repository in: "
            )
            prompt_counter += 1

        if source_url and commit_hash and auditors and organization:
            break
        print("Please fill in all the details.")
    return source_url, target_repo_name, commit_hash, auditors, organization


def try_clone_repo(
    github_token: str,
    organization: str,
    target_repo_name: str,
    source_repo_name: str,
    source_username: str,
    repo_path: str,
    commit_hash: str,
) -> Repository:
    github_object = Github(github_token)
    github_org = github_object.get_organization(organization)
    repo = None
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
        elif result.returncode == 128:
            repo = create_and_clone_repo(
                github_token,
                github_org,
                organization,
                target_repo_name,
                source_repo_name,
                source_username,
                repo_path,
                commit_hash,
            )
    except subprocess.CalledProcessError as e:
        if e.returncode == 128:
            repo = create_and_clone_repo(
                github_token,
                github_org,
                organization,
                target_repo_name,
                source_repo_name,
                source_username,
                repo_path,
                commit_hash,
            )
        else:
            # Handle other errors or exceptions as needed
            log.error(f"Error checking if repository exists: {e}")
            exit()

    if repo is None:
        log.error("Error creating repo.")
        exit()

    return repo


def create_and_clone_repo(
    github_token: str,
    github_org: Organization,
    organization: str,
    target_repo_name: str,
    source_repo_name: str,
    source_username: str,
    repo_path: str,
    commit_hash: str,
) -> Repository:
    try:
        repo = github_org.create_repo(target_repo_name, private=True)
    except GithubException as e:
        log.error(f"Error creating remote repository: {e}")

    try:
        print(f"Cloning {source_repo_name}...")
        subprocess.run(
            [
                "git",
                "clone",
                f"https://{github_token}@github.com/{source_username}/{source_repo_name}.git",
                repo_path,
            ], check=False
        )

    except GithubException as e:
        log.error(f"Error cloning repository: {e}")
        repo.delete()
        exit()

    try:
        subprocess.run(["git", "-C", repo_path, "fetch", "origin"], check=False)

        # Identify the branch containing the commit using `git branch --contains`
        completed_process = subprocess.run(
            ["git", "-C", repo_path, "branch", "-r", "--contains", commit_hash],
            text=True,
            capture_output=True,
            check=True,
        )

        filtered_branches = [
            b
            for b in completed_process.stdout.strip().split("\n")
            if not "origin/HEAD ->" in b
        ]
        branches = [b.split("/", 1)[1] for b in filtered_branches]

        if not branches:
            raise Exception(f"Commit {commit_hash} not found in any branch")

        if len(branches) > 1:
            # Prompt the user to choose the branch
            print("The commit is found on multiple branches:")
            for i, branch in enumerate(branches):
                print(f"{i+1}. {branch}")

            while True:
                try:
                    branch_index = int(
                        input("Enter the number of the branch to create the tag: ")
                    )
                    if branch_index < 1 or branch_index > len(branches):
                        raise ValueError("Invalid branch index")
                    branch = branches[branch_index - 1]
                    break
                except ValueError:
                    print("Invalid branch index. Please enter a valid index.")
        else:
            branch = branches[0]

        # Fetch the branch containing the commit hash
        subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "fetch",
                "origin",
                branch + ":refs/remotes/origin/" + branch,
            ], check=False
        )

        # Checkout the branch containing the commit hash
        subprocess.run(["git", "-C", repo_path, "checkout", branch], check=False)

        # Update the origin remote
        subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "remote",
                "set-url",
                "origin",
                f"https://{github_token}@github.com/{organization}/{target_repo_name}.git",
            ], check=False
        )

        # Push the branch to the remote audit repository as 'main'
        # subprocess.run(f"git -C {repo_path} push -u origin {branch}:{MAIN_BRANCH_NAME}")
        subprocess.run(
            [
                "git",
                "-C",
                repo_path,
                "push",
                "-u",
                "origin",
                f"{branch}:{MAIN_BRANCH_NAME}",
            ], check=False
        )

    except Exception as e:
        log.error(f"Error extracting branch of commit hash: {e}")
        repo.delete()
        exit()

    return repo


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
    except GithubException as e:
        finding_file = None

    # If finding.md already exists, leave it be. Otherwise, create the file.
    if finding_file is None:
        repo.create_file(
            ".github/ISSUE_TEMPLATE/finding.md", "finding.md", ISSUE_TEMPLATE
        )
    return repo


def delete_default_labels(repo) -> Repository:
    log.info("Deleting default labels...")
    for label_name in DEFAULT_LABELS:
        try:
            label = repo.get_label(label_name)
            log.info(f"Deleting {label}...")
            label.delete()
        except Exception as e:
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


if __name__ == "__main__":
    create_audit_repo()
