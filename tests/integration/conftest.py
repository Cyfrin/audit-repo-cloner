"""
Fixtures and utilities for GitHub-based integration tests.
"""
import json
import os
import shutil
import stat
import tempfile
import time
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from github import Github, GithubException


def handle_remove_readonly(func, path, exc):
    """Handle read-only files when removing directories, particularly on Windows."""
    excvalue = exc[1]
    if func in (os.rmdir, os.remove, os.unlink) and excvalue.errno == 13:  # Permission denied
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IEXEC)
            func(path)
        except Exception as e:
            print(f"Failed to handle read-only file {path}: {e}")
    else:
        raise exc[1]


def force_delete(path):
    """Force delete a file or directory, even if it's read-only or locked."""
    if not os.path.exists(path):
        return

    if os.path.isfile(path):
        try:
            os.chmod(path, stat.S_IWRITE | stat.S_IEXEC)
            os.unlink(path)
        except Exception as e:
            print(f"Failed to remove file {path}: {e}")
    else:
        try:
            # Try to use rmtree first
            shutil.rmtree(path, ignore_errors=False, onerror=handle_remove_readonly)
        except Exception as e:
            print(f"Failed to remove directory using rmtree {path}: {e}")

            # If that fails, try a more aggressive approach
            try:
                # On Windows, try to use cmd to force delete
                if os.name == "nt":
                    os.system(f'rmdir /S /Q "{path}"')
                else:
                    os.system(f'rm -rf "{path}"')
            except Exception as e:
                print(f"Failed to force remove directory {path}: {e}")

                # As a last resort, try removing files one by one
                try:
                    for root, dirs, files in os.walk(path, topdown=False):
                        for name in files:
                            full_path = os.path.join(root, name)
                            try:
                                os.chmod(full_path, stat.S_IWRITE | stat.S_IEXEC)
                                os.unlink(full_path)
                            except Exception as e:
                                print(f"Failed to remove file {full_path}: {e}")
                        for name in dirs:
                            full_path = os.path.join(root, name)
                            try:
                                os.chmod(full_path, stat.S_IWRITE | stat.S_IEXEC)
                                os.rmdir(full_path)
                            except Exception as e:
                                print(f"Failed to remove directory {full_path}: {e}")
                except Exception as e:
                    print(f"Failed during individual file cleanup of {path}: {e}")


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

    # Create GitHub client with verbose logging
    g = Github(github_token)
    print("DEBUG: Created GitHub client")
    return g


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

        # Add a README file instead of a Python file
        source_repo.create_file("README.md", "Add README", "# Test Repository\nThis is a test repository for integration testing.")

        # Add Solidity smart contract files for testing
        solidity_code = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleStorage {
    uint256 private value;

    function store(uint256 _value) public {
        value = _value;
    }

    function retrieve() public view returns (uint256) {
        return value;
    }
}
"""
        source_repo.create_file("contracts/SimpleStorage.sol", "Add SimpleStorage contract", solidity_code)

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
            if os.path.exists(temp_dir):
                print(f"Removing temporary directory: {temp_dir}")
                try:
                    force_delete(temp_dir)
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

            # Add a README file instead of a Python file
            repo.create_file(f"README.md", "Add README", f"# Test Repository {i}\nThis is a test repository {i} for integration testing.")

            # Add Solidity smart contract files for testing
            solidity_code = """
// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract SimpleStorage {
    uint256 private value;

    function store(uint256 _value) public {
        value = _value;
    }

    function retrieve() public view returns (uint256) {
        return value;
    }
}
"""
            repo.create_file("contracts/SimpleStorage.sol", "Add SimpleStorage contract", solidity_code)

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
            if os.path.exists(temp_dir):
                print(f"Removing temporary directory: {temp_dir}")
                try:
                    force_delete(temp_dir)
                except Exception as e:
                    print(f"Error removing temporary directory {temp_dir}: {e}")
