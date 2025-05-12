"""
Fixtures and utilities for GitHub-based integration tests.
"""
import json
import os
import shutil
import tempfile
import time
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from github import Github, GithubException


# Load environment variables from .env file if present
def load_env_files():
    """Load environment variables from .env files."""
    # First try to load from project root
    root_dir = Path(__file__).resolve().parent.parent.parent

    # Try loading from various env files in order of preference
    env_files = [
        root_dir / ".env",
        root_dir / ".env.test",
        root_dir / ".env.local",
    ]

    for env_file in env_files:
        if env_file.exists():
            load_dotenv(env_file)
            print(f"Loaded environment from {env_file}")
            break


# Load environment variables before tests run
load_env_files()


def random_repo_name(prefix="test-"):
    """Generate a random repository name."""
    return f"{prefix}{uuid.uuid4().hex[:8]}"


@pytest.fixture
def github_client():
    """Create a GitHub client using the test token."""
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    if not github_token:
        pytest.skip("TEST_GITHUB_TOKEN environment variable not set")

    return Github(github_token)


@pytest.fixture
def github_org(github_client):
    """Get the GitHub organization for testing."""
    org_name = os.environ.get("TEST_GITHUB_ORG")
    if not org_name:
        pytest.skip("TEST_GITHUB_ORG environment variable not set")

    return github_client.get_organization(org_name)


@pytest.fixture
def temp_github_repos(github_client, github_org):
    """
    Fixture to create temporary GitHub repositories for testing.

    Creates:
    - A source repository with a GitHub Actions workflow
    - A temporary directory for configs and local operations

    Yields a dictionary with repository info
    Cleans up all created repositories after tests
    """
    # List to track repos to clean up
    test_repos = []
    temp_dirs = []

    # Create a source repo with GitHub Actions workflow
    source_repo_name = random_repo_name("source-repo-")
    try:
        source_repo = github_org.create_repo(source_repo_name, private=True)
        test_repos.append(source_repo)

        # Sleep to ensure repo is fully created before adding files
        time.sleep(3)

        # Create GitHub Actions workflow in the source repo
        workflow_content = """name: Test Workflow
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: echo "Test workflow"
"""
        source_repo.create_file(".github/workflows/test.yml", "Add test workflow", workflow_content)

        # Add an actions workflow in a non-standard location
        source_repo.create_file(".github/actions/custom-action/action.yml", "Add custom action", "name: 'Custom Action'\nruns:\n  using: 'composite'\n  steps:\n    - run: echo 'Custom action'")

        # Add some code to the source repo
        source_repo.create_file("test.py", "Add test file", "print('Hello, world!')")

        # Get the latest commit hash
        commit_hash = source_repo.get_commits()[0].sha

        # Create a temporary directory for the audit repo
        temp_dir = tempfile.mkdtemp()
        temp_dirs.append(temp_dir)

        # Create target repo name
        target_repo_name = random_repo_name("audit-repo-")

        # Create config file
        config = {"targetRepoName": target_repo_name, "projectTitle": "[Test] Audit Project", "auditors": "tester1 tester2", "repositories": [{"sourceUrl": source_repo.html_url, "commitHash": commit_hash, "subFolder": "source-repo"}]}

        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Store config and test info
        test_info = {"source_repo_name": source_repo_name, "source_repo": source_repo, "target_repo_name": target_repo_name, "commit_hash": commit_hash, "org_name": github_org.login, "temp_dir": temp_dir, "config_path": config_path, "config": config, "test_repos": test_repos}

        yield test_info

    finally:
        # Cleanup - delete all test repositories
        for repo in test_repos:
            try:
                print(f"Deleting test repository: {repo.name}")
                repo.delete()
            except GithubException as e:
                print(f"Error deleting repository {repo.name}: {e}")

        # Remove temporary directories
        for temp_dir in temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Error removing temporary directory {temp_dir}: {e}")


@pytest.fixture
def multi_repo_setup(github_client, github_org):
    """
    Fixture to create multiple source repositories for testing.

    Creates:
    - Two source repositories, each with GitHub Actions workflows
    - A temporary directory for configs and local operations

    Yields a dictionary with repository info
    Cleans up all created repositories after tests
    """
    # List to track repos to clean up
    test_repos = []
    temp_dirs = []

    try:
        sources = []
        for i in range(2):
            # Create a source repo with GitHub Actions workflow
            repo_name = random_repo_name(f"source-repo-{i}-")
            repo = github_org.create_repo(repo_name, private=True)
            test_repos.append(repo)

            # Sleep to ensure repo is fully created before adding files
            time.sleep(3)

            # Create GitHub Actions workflow in the source repo
            workflow_content = f"""name: Test Workflow {i}
on: [push]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: echo "Test workflow {i}"
"""
            repo.create_file(".github/workflows/test.yml", "Add test workflow", workflow_content)

            # Add some code to the source repo
            repo.create_file(f"test{i}.py", "Add test file", f"print('Hello from repo {i}!')")

            # Get the latest commit hash
            commit_hash = repo.get_commits()[0].sha

            sources.append({"repo": repo, "name": repo_name, "commit_hash": commit_hash, "sub_folder": f"source-repo-{i}"})

        # Create a temporary directory for the audit repo
        temp_dir = tempfile.mkdtemp()
        temp_dirs.append(temp_dir)

        # Create target repo name
        target_repo_name = random_repo_name("multi-audit-repo-")

        # Create config file
        config = {"targetRepoName": target_repo_name, "projectTitle": "[Test] Multi-Repo Audit Project", "auditors": "tester1 tester2", "repositories": [{"sourceUrl": source["repo"].html_url, "commitHash": source["commit_hash"], "subFolder": source["sub_folder"]} for source in sources]}

        config_path = os.path.join(temp_dir, "config.json")
        with open(config_path, "w") as f:
            json.dump(config, f)

        # Store config and test info
        test_info = {"sources": sources, "target_repo_name": target_repo_name, "org_name": github_org.login, "temp_dir": temp_dir, "config_path": config_path, "config": config, "test_repos": test_repos}

        yield test_info

    finally:
        # Cleanup - delete all test repositories
        for repo in test_repos:
            try:
                print(f"Deleting test repository: {repo.name}")
                repo.delete()
            except GithubException as e:
                print(f"Error deleting repository {repo.name}: {e}")

        # Remove temporary directories
        for temp_dir in temp_dirs:
            try:
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir)
            except Exception as e:
                print(f"Error removing temporary directory {temp_dir}: {e}")
