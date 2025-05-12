"""
Integration tests for verifying GitHub Actions removal functionality.
"""
import os

from github import Github

from audit_repo_cloner.create_audit_repo import create_audit_repo
from tests.integration.test_utils import check_file_exists, check_git_history, clone_repo_to_temp, get_all_github_action_paths


def test_github_actions_removal(temp_github_repos):
    """
    Test that GitHub Actions are properly removed during repository cloning.

    This test:
    1. Creates a source repository with GitHub Actions workflow files
    2. Creates an audit repository using the tool
    3. Verifies that the GitHub Actions files are not present in the audit repository
    """
    # Extract test data
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    assert github_token is not None, "TEST_GITHUB_TOKEN environment variable must be set"

    source_repo = temp_github_repos["source_repo"]
    target_repo_name = temp_github_repos["target_repo_name"]
    org_name = temp_github_repos["org_name"]
    config_path = temp_github_repos["config_path"]
    temp_dir = temp_github_repos["temp_dir"]

    # Verify the source repo has GitHub Actions workflows
    assert check_file_exists(source_repo, ".github/workflows/test.yml"), "Source repo should have a workflow file"
    assert check_file_exists(source_repo, ".github/actions/custom-action/action.yml"), "Source repo should have an action.yml file"

    # Run the audit repo cloner
    print("Running the audit repo cloner...")
    result = create_audit_repo(config_path, github_token=github_token)

    assert result is True, "Audit repo creation should succeed"

    # Get the GitHub client
    github = Github(github_token)

    # Get the target repo
    try:
        target_repo = github.get_organization(org_name).get_repo(target_repo_name)
        temp_github_repos["test_repos"].append(target_repo)  # Add for cleanup

        # Verify the target repo was created
        assert target_repo is not None, f"Target repo {target_repo_name} should exist"

        # Clone the target repo for detailed inspection
        target_repo_path = clone_repo_to_temp(target_repo.clone_url, github_token, temp_dir)

        # Check specifically for source repo actions in the expected subtree location
        source_in_target_path = os.path.join(target_repo_path, "source-repo")
        assert os.path.exists(source_in_target_path), "Source repo should be in the target repo"

        # Check for any GitHub Actions files in the source repo subtree
        action_paths = get_all_github_action_paths(source_in_target_path)

        # There should be no GitHub Actions files in the source repo subtree
        assert len(action_paths) == 0, f"Found GitHub Actions files in source repo subtree: {action_paths}"

        # Check for commit messages that indicate GitHub Actions were removed
        commit_patterns = [
            r"Add .+ at commit",  # Standard commit message pattern
        ]

        commit_matches = check_git_history(target_repo_path, commit_patterns)
        found_subtree_commit = False

        # Check that we have at least one matching commit
        for pattern, commits in commit_matches.items():
            if any(commits):
                found_subtree_commit = True
                break

        assert found_subtree_commit, "Should find at least one subtree addition commit"

    finally:
        # Cleanup is handled by the fixture
        pass


def test_multi_repo_actions_removal(multi_repo_setup):
    """
    Test that GitHub Actions are properly removed when cloning multiple source repositories.

    This test:
    1. Creates multiple source repositories with GitHub Actions
    2. Creates an audit repository using the tool
    3. Verifies that GitHub Actions are removed from all source repositories
    """
    # Extract test data
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    assert github_token is not None, "TEST_GITHUB_TOKEN environment variable must be set"

    sources = multi_repo_setup["sources"]
    target_repo_name = multi_repo_setup["target_repo_name"]
    org_name = multi_repo_setup["org_name"]
    config_path = multi_repo_setup["config_path"]
    temp_dir = multi_repo_setup["temp_dir"]

    # Verify each source repo has GitHub Actions workflows
    for source in sources:
        repo = source["repo"]
        assert check_file_exists(repo, ".github/workflows/test.yml"), f"Source repo {repo.name} should have a workflow file"

    # Run the audit repo cloner
    print("Running the audit repo cloner for multiple repositories...")
    result = create_audit_repo(config_path, github_token=github_token)

    assert result is True, "Audit repo creation should succeed"

    # Get the GitHub client
    github = Github(github_token)

    # Get the target repo
    try:
        target_repo = github.get_organization(org_name).get_repo(target_repo_name)
        multi_repo_setup["test_repos"].append(target_repo)  # Add for cleanup

        # Verify the target repo was created
        assert target_repo is not None, f"Target repo {target_repo_name} should exist"

        # Clone the target repo for detailed inspection
        target_repo_path = clone_repo_to_temp(target_repo.clone_url, github_token, temp_dir)

        # Check each source repo in the target
        for source in sources:
            subfolder = source["sub_folder"]
            source_in_target_path = os.path.join(target_repo_path, subfolder)

            assert os.path.exists(source_in_target_path), f"Source repo {subfolder} should be in the target repo"

            # Check for any GitHub Actions files in this source repo subtree
            action_paths = get_all_github_action_paths(source_in_target_path)

            # There should be no GitHub Actions files in the source repo subtree
            assert len(action_paths) == 0, f"Found GitHub Actions files in {subfolder}: {action_paths}"

        # Check for GitHub Actions in the Cyfrin report generator subtree
        report_generator_path = os.path.join(target_repo_path, "report-generator-template")
        if os.path.exists(report_generator_path):
            # The report generator might have legitimate GitHub Actions - we don't remove those
            actions_paths = get_all_github_action_paths(report_generator_path)
            print(f"Report generator actions (these should remain): {actions_paths}")

    finally:
        # Cleanup is handled by the fixture
        pass
