import os
import shutil
from datetime import date
from typing import List, Optional, Tuple
from github import Github, GithubException, Repository
from dotenv import load_dotenv
from create_action import create_action
from create_secret import create_secret
import click
import subprocess
import logging as log
import yaml
from __version__ import __version__, __title__

from constants import (
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
SUBTREE_URL = "https://github.com/ChainAccelOrg/report-generator-template.git"
SUBTREE_NAME = "report-generator-template"
SUBTREE_PATH_PREFIX = "cyfrin-report"
GITHUB_WORKFLOW_ACTION_NAME = "generate-report"


@click.command()
@click.version_option(
    version=__version__,
    prog_name=__title__,
)
@click.option("--config", type=click.Path(exists=True), help="Path to YAML config file")
@click.option(
    "--prompt/--no-prompt",
    default=True,
    help="Have this CLI be interactive by prompting or pass in args via the command.",
)
@click.option("--source-url", default=None, help="Source repository URL.")
@click.option("--commit-hash", default=None, help="Audit commit hash.")
@click.option(
    "--auditors", default=None, help="Names of the auditors (separated by spaces)."
)
@click.option(
    "--github-token",
    default=os.getenv("GITHUB_TOKEN"),
    help="Your GitHub developer token to make API calls.",
)
@click.option(
    "--organization",
    default=os.getenv("GITHUB_ORGANIZATION"),
    help="Your GitHub organization name in which to clone the repo.",
)
@click.option(
    "--repo-path-dir",
    default="/tmp",
    help="The path to the directory where the cloned repo will be stored. If left to the default, the repo will be attempted to be deleted after the script is run.",
)
def create_audit_repo(
    config: str,
    prompt: bool,
    source_url: str,
    commit_hash:str,
    auditors: str,
    github_token: str,
    organization: str,
    repo_path_dir: str,
):
    """This function clones a target repository and prepares it for a Cyfrin audit using the provided arguments.
    If the prompt flag is set to true (default), the user will be prompted for the source repository URL and auditor names.
    If the prompt flag is set to false, the function will use the provided click arguments for the source repository URL and auditor names.

    Args:
        prompt (bool): Determines if the script should use default prompts for input or the provided click arguments.
        source_url (str): The URL of the source repository to be cloned and prepared for the Cyfrin audit.
        auditors (str): A space-separated list of auditor names who will be assigned to the audit.
        github_token (str): The GitHub developer token to make API calls.
        organization (str): The GitHub organization to create the audit repository in.
        repo_path_dir (str): The path to the directory where the cloned repo will be stored. If left to the default, the repo will be attempted to be deleted after the script is run.

    Returns:
        None
    """
    if config:
        (source_url, commit_hash, auditors, github_token, organization) = load_config(
            config,
            source_url=source_url,
            commit_hash=commit_hash,
            auditors=auditors,
            github_token=github_token,
            organization=organization,
        )
    if prompt:
        source_url, commit_hash, auditors, organization = prompt_for_details(
            source_url, commit_hash, auditors, organization
        )
    if not source_url or not commit_hash or not auditors or not organization:
        raise click.UsageError(
            "Source URL, commit hash, organization, and auditors must be provided either through --prompt, config, or as options."
        )
    if not github_token:
        raise click.UsageError(
            "GitHub token must be provided either through config or environment variable."
        )
    source_url = source_url.rstrip(".git")
    url_parts = source_url.split("/")
    source_username = url_parts[-2]
    source_repo_name = url_parts[-1]
    auditors_list: List[str] = [a.strip() for a in auditors.split(" ")]

    repo = get_or_clone_repo(
        github_token,
        organization,
        source_repo_name,
        source_username,
        repo_path_dir,
    )

    tag = repo.create_git_tag(
        tag="cyfrin-audit",
        message="Cyfrin audit tag",
        object=commit_hash,
        type="commit",
    )

    # Now create a reference to this tag in the repository
    repo.create_git_ref(ref=f"refs/tags/{tag.tag}", sha=tag.sha)

    repo = add_issue_template_to_repo(repo)
    repo = replace_labels_in_repo(repo)
    repo = create_branches_for_auditors(repo, auditors_list)
    main_branch = repo.get_branch(MAIN_BRANCH_NAME)
    repo = create_report_branch(repo, main_branch)

    subtree_path = f"{SUBTREE_PATH_PREFIX}/{SUBTREE_NAME}"

    repo_path = os.path.abspath(f"{repo_path_dir}/{source_repo_name}")
    if not os.path.exists(f"{repo_path}/{SUBTREE_PATH_PREFIX}"):
        add_subtree(repo, source_repo_name, repo_path_dir, subtree_path)

    set_up_ci(repo, subtree_path, github_token)
    set_up_project_board(repo, source_username, source_repo_name)
    print("Done!")
    

def add_subtree(repo: Repository, source_repo_name: str, repo_path_dir: str, subtree_path: str):
    # Add report-generator-template as a subtree

    repo_path = os.path.abspath(f"{repo_path_dir}/{source_repo_name}")
    if not os.path.exists(repo_path):
        os.makedirs(repo_path)
    try:
        print(f"Adding subtree {SUBTREE_NAME}...")

        # Pull the latest changes from the origin
        subprocess.run(
            f"git -C {repo_path} pull origin {REPORT_BRANCH_NAME} --rebase",
            shell=True,
            check=True,
        )
        subprocess.run(
            f"git -C {repo_path} checkout {REPORT_BRANCH_NAME}", shell=True, check=True
        )

        # Add the subtree to the repo
        subprocess.run(
            f"git -C {repo_path} subtree add --prefix {subtree_path} {SUBTREE_URL} main --squash",
            shell=True,
            check=True,
        )
        os.makedirs(f"{repo_path}/.github/workflows", exist_ok=True)
        subprocess.run(
            f"mv {repo_path}/{subtree_path}/.github/workflows/main.yml {repo_path}/.github/workflows/main.yml",
            shell=True,
            check=True,
        )
        subprocess.run(f"git -C {repo_path} add .", shell=True, check=True)
        subprocess.run(
            f"git -C {repo_path}  commit -m 'install: {SUBTREE_NAME}'",
            shell=True,
            check=True,
        )

        # Push the changes back to the origin
        subprocess.run(f"git -C {repo_path} push", shell=True, check=True)

        # Remove the local directory
        shutil.rmtree(repo_path)

        print(
            f"The subtree {SUBTREE_NAME} has been added to {repo.name} on branch {REPORT_BRANCH_NAME}"
        )

    except GithubException as e:
        log.error(f"Error adding subtree: {e}")
        exit()


def set_up_ci(repo, subtree_path: str, github_token):
    try:
        create_secret(repo, "GITHUB_TOKEN", github_token)
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


def set_up_project_board(repo, source_username: str, source_repo_name: str):
    try:
        repo.edit(has_projects=True)
        project = repo.create_project(
            f"{source_username}/{source_repo_name}",
            body=f"A collaborative board for the {source_username}/{source_repo_name} audit",
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


def load_config(
    config: str,
    source_url: Optional[str] = None,
    auditors: Optional[str] = None,
    github_token: Optional[str] = None,
    organization: Optional[str] = None,
) -> Tuple[str, str, str, str]:
    """Loads the configuration file and returns the values.

    Args:
        config (str): The path to the configuration file.
        source_url (Optional[str], optional): The URL you want to download. Defaults to None.
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
    return source_url, auditors, github_token, organization


def prompt_for_details(source_url: str, commit_hash: str, auditors: str, organization: str):
    while True:
        if not source_url:
            source_url = input(
                "Hello! This script will clone target repository and prepare it for a Cyfrin audit. Please enter the following details:\n\n1) Source repo url: "
            )
        if not commit_hash:
            commit_hash = input(
                "\n2) Audit commit hash (be sure to copy the full SHA): "
            )
        if not auditors:
            auditors = input(
                "\n3) Enter the names of the auditors (separated by spaces): "
            )
        if not organization:
            organization = input(
                "\n4) Enter the name of the organization to create the audit repository in: "
            )

        if source_url and auditors and organization:
            break
        print("Please fill in all the details.")
    return source_url, commit_hash, auditors, organization


def get_or_clone_repo(
    github_token,
    organization,
    source_repo_name,
    source_username,
    repo_path_dir,
) -> Repository:
    github_object = Github(github_token)
    github_org = github_object.get_organization(organization)
    repo_path = os.path.abspath(f"{repo_path_dir}/{source_repo_name}")
    try:
        repo = github_object.get_repo(f"{organization}/{source_repo_name}")
        print(f"Cloning {source_repo_name}...")
        subprocess.run(
            [
                "git",
                "clone",
                f"https://{github_token}@github.com/{organization}/{source_repo_name}.git",
                repo_path,
            ]
        )
        return repo
    except GithubException as e:
        if e.status == 404:
            repo = None
        else:
            log.error(f"Error checking if repository exists: {e}")
            exit()

    if repo is None:
        try:
            repo = github_org.create_repo(source_repo_name, private=True)
        except GithubException as e:
            log.error(e)

        try:
            print(f"Cloning {source_repo_name}...")
            subprocess.run(
                [
                    "git",
                    "clone",
                    f"https://{github_token}@github.com/{source_username}/{source_repo_name}.git",
                    repo_path,
                ]
            )

            subprocess.run(["git", "-C", repo_path, "commit", "-m", "initial commit"])

            subprocess.run(
                [
                    "git",
                    "-C",
                    repo_path,
                    "remote",
                    "set-url",
                    "origin",
                    f"https://{github_token}@github.com/{organization}/{source_repo_name}.git",
                ]
            )

            subprocess.run(["git", "-C", repo_path, "push", "-u", "origin", "main"])

        except GithubException as e:
            log.error(f"Error cloning repository: {e}")
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
    for label in DEFAULT_LABELS:
        try:
            label = repo.get_label(i)
            label.delete()
            log.info(f"Deleting {label}...")
        except:
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


def create_branches_for_auditors(repo, auditors_list) -> Repository:
    main_branch = repo.get_branch(MAIN_BRANCH_NAME)
    for auditor in auditors_list:
        branch_name = f"audit/{auditor}"
        try:
            repo.create_git_ref(f"refs/heads/{branch_name}", main_branch.commit.sha)
        except GithubException as e:
            if e.status == 422:
                log.warn(f"Branch {branch_name} already exists. Skipping...")
                continue
            else:
                log.error(f"Error creating branch: {e}")
                exit()
    return repo


def replace_labels_in_repo(repo) -> Repository:
    repo = delete_default_labels(repo)
    repo = create_new_labels(repo)
    return repo


def create_report_branch(repo, main_branch) -> Repository:
    try:
        repo.create_git_ref(
            ref=f"refs/heads/{REPORT_BRANCH_NAME}", sha=main_branch.commit.sha
        )
    except GithubException as e:
        if e.status == 422:
            log.warn(f"Branch {REPORT_BRANCH_NAME} already exists. Skipping...")
        else:
            log.error(f"Error creating branch: {e}")
            exit()
    return repo


if __name__ == "__main__":
    create_audit_repo()
