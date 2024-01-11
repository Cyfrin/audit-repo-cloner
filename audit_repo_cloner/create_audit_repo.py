import os
from datetime import date
from typing import List, Optional, Tuple
from github import Github, GithubException, Repository, Organization
from dotenv import load_dotenv
from create_action import create_action
from github_project_utils import clone_project
import click
import subprocess
import tempfile
import logging as log
import re
from __version__ import __version__, __title__

from constants import (
    ISSUE_TEMPLATE,
    DEFAULT_LABELS,
    SEVERITY_DATA,
    PROJECT_TEMPLATE_ID,
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
@click.option("--source-url", help="Source repository URL.", default=os.getenv("SOURCE_REPO_URL"))
@click.option("--target-repo-name", help="Target repository name (leave blank to use source repo name).", default=os.getenv("TARGET_REPO_NAME"))
@click.option("--commit-hash", help="Audit commit hash.", default=os.getenv("COMMIT_HASH"))
@click.option("--auditors", help="Names of the auditors (separated by spaces).", default=os.getenv("ASSIGNED_AUDITORS"))
@click.option("--github-token", help="Your GitHub developer token to make API calls.", default=os.getenv("GITHUB_ACCESS_TOKEN"))
@click.option("--organization", help="Your GitHub organization name in which to clone the repo.", default=os.getenv("GITHUB_ORGANIZATION"))
@click.option("--project-title", help="Title of the new project board on GitHub.", default=os.getenv("PROJECT_TITLE"))
def create_audit_repo(
    source_url: str = None,
    target_repo_name: str = None,
    commit_hash: str = None,
    auditors: str = None,
    github_token: str = None,
    organization: str = None,
    project_title: str = None
):
    """This function clones a target repository and prepares it for a Cyfrin audit using the provided arguments.

    Args:
        source_url (str): The URL of the source repository to be cloned and prepared for the Cyfrin audit.
        target_repo_name (str): The name of the target repository to be created.
        auditors (str): A space-separated list of auditor names who will be assigned to the audit.
        github_token (str): The GitHub developer token to make API calls.
        organization (str): The GitHub organization to create the audit repository in.
        project_title (str): The title of the GitHub project board.

    Returns:
        None
    """

    (
        source_url,
        target_repo_name,
        commit_hash,
        auditors,
        github_token,
        organization,
        project_title
    ) = prompt_for_details(
        source_url,
        target_repo_name,
        commit_hash,
        auditors,
        github_token,
        organization,
        project_title
    )
    if not source_url or not commit_hash or not auditors or not organization:
        raise click.UsageError(
            "Source URL, commit hash, organization, and auditors must be provided either through environment variables, or as options."
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
    project_template_id = PROJECT_TEMPLATE_ID

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
        set_up_project_board(repo, github_token, organization, target_repo_name, project_template_id, project_title)


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


def prompt_for_details(
    source_url: str,
    target_repo_name: str,
    commit_hash: str,
    auditors: str,
    github_token: str,
    organization: str,
    project_title: str
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
        if not github_token:
            github_token = input(
                f"\n{prompt_counter}) Enter your Github token: "
            )
            prompt_counter += 1
        if not organization:
            organization = input(
                f"\n{prompt_counter}) Enter the name of the organization to create the audit repository in: "
            )
            prompt_counter += 1
        if not project_title:
            project_title = input(
                f"\n{prompt_counter}) Enter the title of the GitHub project board: "
            )
            prompt_counter += 1

        if source_url and commit_hash and auditors and github_token and organization and project_title:
            break
        print("Please fill in all the details.")
    return source_url, target_repo_name, commit_hash, auditors, github_token, organization, project_title


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
        exit()

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

# IMPORTANT: project creation via REST API is not supported anymore
# https://stackoverflow.com/questions/73268885/unable-to-create-project-in-repository-or-organisation-using-github-rest-api
# we use a non-standard way to access GitHub's GraphQL
def set_up_project_board(
        repo: Repository,
        github_token: str,
        organization: str,
        target_repo_name: str,
        project_template_id: str,
        project_title: str = "DEFAULT PROJECT"
    ):
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
