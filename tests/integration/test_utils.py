"""
Utility functions for integration tests.
"""
import os
import re
import subprocess
from typing import Dict, List

from github import Repository


def check_file_exists(repo: Repository, path: str) -> bool:
    """Check if a file exists in the repository."""
    try:
        repo.get_contents(path)
        return True
    except Exception:
        return False


def normalize_path(path: str) -> str:
    """Normalize path for consistent handling across OS platforms."""
    # Git always uses forward slashes, so ensure paths are using forward slashes
    return path.replace("\\", "/")


def clone_repo_to_temp(repo_url: str, github_token: str, temp_dir: str) -> str:
    """Clone a repository to a temporary directory and return the path."""
    # Add authentication to the URL for private repositories
    authenticated_url = repo_url.replace("https://", f"https://{github_token}@")

    # Clone the repo
    repo_name = repo_url.split("/")[-1].replace(".git", "")
    repo_path = os.path.join(temp_dir, repo_name)

    print(f"DEBUG: Cloning from {repo_url} (auth URL redacted)")
    print(f"DEBUG: Will clone to path: {repo_path}")

    # Clone the repository
    clone_result = subprocess.run(["git", "clone", authenticated_url, repo_path], capture_output=True, text=True, check=False)

    if clone_result.returncode != 0:
        print(f"DEBUG: Clone failed with returncode {clone_result.returncode}")
        print(f"DEBUG: stderr = {clone_result.stderr}")
        print(f"DEBUG: stdout = {clone_result.stdout}")
    else:
        print(f"DEBUG: Clone succeeded to path {repo_path}")
        # List the contents to diagnose issues
        print("DEBUG: Contents of cloned repo:")
        try:
            for root, dirs, files in os.walk(repo_path):
                for file in files:
                    print(f"  {os.path.join(root, file)}")
        except Exception as e:
            print(f"DEBUG: Error listing files: {e}")

    return repo_path


def get_all_github_action_paths(repo_path: str) -> List[str]:
    """
    Find all GitHub Actions files in a local repository.

    Returns a list of paths to GitHub Actions files.
    Includes traditional workflows directory and action.yml files.
    """
    workflow_dir = os.path.join(repo_path, ".github", "workflows")
    actions_paths = []

    # Check for .github/workflows directory
    if os.path.exists(workflow_dir):
        for root, _, files in os.walk(workflow_dir):
            for file in files:
                if file.endswith((".yml", ".yaml")):
                    rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                    actions_paths.append(rel_path)

    # Check for action.yml files which can be anywhere in the repo
    for root, _, files in os.walk(repo_path):
        for file in files:
            if file == "action.yml" or file == "action.yaml":
                rel_path = os.path.relpath(os.path.join(root, file), repo_path)
                # Exclude node_modules and similar directories
                if not any(part in rel_path for part in ["node_modules", "venv", ".git"]):
                    actions_paths.append(rel_path)

    return actions_paths


def check_git_history(repo_path: str, patterns: List[str]) -> Dict[str, List[str]]:
    """
    Check git history for specific patterns in commit messages.

    Args:
        repo_path: Path to the git repository
        patterns: List of regex patterns to search for in commit messages

    Returns:
        Dictionary mapping patterns to matching commit messages
    """
    result = {pattern: [] for pattern in patterns}

    # Get all commit messages
    git_log = subprocess.run(["git", "log", "--pretty=format:%s"], cwd=repo_path, capture_output=True, text=True, check=True)

    commit_messages = git_log.stdout.splitlines()

    # Check each message against each pattern
    for message in commit_messages:
        for pattern in patterns:
            if re.search(pattern, message):
                result[pattern].append(message)

    return result
