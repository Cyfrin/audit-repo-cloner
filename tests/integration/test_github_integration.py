"""
Integration tests for audit repository cloning functionality.
This file contains all GitHub integration tests for the audit-repo-cloner tool.
Tests include repository creation, GitHub Actions removal, multi-repository cloning,
branch setup, and project board configuration.
"""
import os
import re
import subprocess
import time

from github import Github

from audit_repo_cloner.create_audit_repo import _create_audit_repo
from audit_repo_cloner.github_project_utils import verify_project_exists
from tests.integration.test_utils import check_file_exists, check_git_history, clone_repo_to_temp, get_all_github_action_paths, normalize_path

TIME_DELAY_BETWEEN_ACTIONS = 5


def test_single_repo_cloning(temp_github_repos):
    """
    Test comprehensive functionality for a single repository.

    This test:
    1. Creates a source repository with GitHub Actions and smart contract files
    2. Creates an audit repository using the tool
    3. Verifies that:
       - GitHub Actions files are properly removed
       - Smart contract files are properly cloned
       - All relevant branches are created
       - Report workflow is created
    """
    # Extract test data
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    assert github_token is not None, "TEST_GITHUB_TOKEN environment variable must be set"

    source_repo = temp_github_repos["source_repo"]
    target_repo_name = temp_github_repos["target_repo_name"]
    org_name = temp_github_repos["org_name"]
    config_path = temp_github_repos["config_path"]
    temp_dir = temp_github_repos["temp_dir"]
    auditors = temp_github_repos["config"]["auditors"].split()
    project_title = temp_github_repos["config"]["projectTitle"]

    # Verify the source repo has GitHub Actions workflows
    assert check_file_exists(source_repo, ".github/workflows/test.yml"), "Source repo should have a workflow file"
    assert check_file_exists(source_repo, ".github/actions/custom-action/action.yml"), "Source repo should have an action.yml file"

    # Verify smart contract file already exists
    assert check_file_exists(source_repo, "contracts/SimpleStorage.sol"), "Source repo should have SimpleStorage.sol contract"

    # Run the audit repo cloner
    print("Running the audit repo cloner...")
    result = _create_audit_repo(config_path, github_token)

    assert result is True, "Audit repo creation should succeed"

    # Wait a bit for GitHub to propagate changes
    print("Waiting for GitHub to propagate changes...")
    time.sleep(TIME_DELAY_BETWEEN_ACTIONS)

    # Get the GitHub client
    github = Github(github_token)

    # Get the target repo
    try:
        target_repo = github.get_organization(org_name).get_repo(target_repo_name)
        temp_github_repos["test_repos"].append(target_repo)  # Add for cleanup

        # Verify the target repo was created
        assert target_repo is not None, f"Target repo {target_repo_name} should exist"

        # Clone the target repo for detailed inspection
        target_repo_path = clone_repo_to_temp(target_repo.clone_url, github_token, temp_dir, full_clone=True)

        # Fetch all branches
        subprocess.run(["git", "fetch", "--all"], cwd=target_repo_path, check=True)

        # 1. Check that source repo has been cloned to the expected location
        source_in_target_path = os.path.join(target_repo_path, "source-repo")

        # Make sure we have the latest changes
        subprocess.run(["git", "fetch", "--all"], cwd=target_repo_path, check=True)
        subprocess.run(["git", "pull", "origin", "main"], cwd=target_repo_path, check=True)

        # Checkout main branch where source-repo is expected to be
        subprocess.run(["git", "checkout", "main"], cwd=target_repo_path, check=True)

        # Check for the source repository
        assert os.path.exists(source_in_target_path), "Source repo should be in the target repo"

        # 2. Verify GitHub Actions removal
        # Check specifically for the problematic files we know should be removed
        github_workflow_path = os.path.join(source_in_target_path, ".github", "workflows", "test.yml")
        github_action_path = os.path.join(source_in_target_path, ".github", "actions", "custom-action", "action.yml")

        assert not os.path.exists(github_workflow_path), f"GitHub workflow file still exists: {github_workflow_path}"
        assert not os.path.exists(github_action_path), f"GitHub action file still exists: {github_action_path}"

        # Extra check to verify no GitHub Actions files remain
        action_paths = get_all_github_action_paths(source_in_target_path)
        if action_paths:
            print(f"WARNING: Unexpected GitHub Actions files found: {action_paths}")

        # 3. Verify smart contract files exist
        contract_path = os.path.join(source_in_target_path, "contracts", "SimpleStorage.sol")
        assert os.path.exists(contract_path), f"SimpleStorage.sol file not found at expected path: {contract_path}"
        print(f"Found SimpleStorage.sol at {os.path.relpath(contract_path, target_repo_path)}")

        # 4. Verify branches
        branches = [branch.name for branch in target_repo.get_branches()]

        # Main branch should exist
        assert "main" in branches, "Main branch should exist"

        # Report branch should exist
        assert "report" in branches, "Report branch should exist"

        # Auditor branches should exist
        for auditor in auditors:
            expected_branch = f"audit/{auditor}"
            assert expected_branch in branches, f"Branch for auditor {auditor} should be created as {expected_branch}"

        # 5. Check report branch contents
        subprocess.run(["git", "checkout", "report"], cwd=target_repo_path, check=True)

        # Add a short delay to ensure file system is fully updated
        print(target_repo_path)
        time.sleep(30)

        # Verify report generator template is present
        report_generator_path = os.path.join(target_repo_path, "cyfrin-report", "report-generator-template")
        assert os.path.exists(report_generator_path), "Report generator template should be present in the report branch"

        # Verify GitHub workflow files exist in report branch
        workflow_path = os.path.join(target_repo_path, ".github", "workflows")
        assert os.path.exists(workflow_path), "GitHub workflows directory should exist in report branch"

        # At least one workflow file should exist
        workflow_files = os.listdir(workflow_path)
        assert len(workflow_files) > 0, "At least one workflow file should exist in the report branch"

        # Check that at least one workflow is for report generation
        report_workflow_exists = False
        for workflow_file in workflow_files:
            with open(os.path.join(workflow_path, workflow_file), "r") as f:
                content = f.read()
                if re.search(r"(generate[_-]report|report[_-]generator)", content, re.IGNORECASE):
                    report_workflow_exists = True
                    break

        assert report_workflow_exists, "A workflow file for report generation should exist"

        # 6. Check project board using GraphQL approach
        # This avoids the deprecated GitHub Projects Classic API
        assert verify_project_exists(github_token, org_name, project_title), f"A project with title containing '{project_title}' should exist"

        # 7. Check for commit messages
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


def test_multi_repo_cloning(multi_repo_setup):
    """
    Test comprehensive functionality with multiple repositories.

    This test:
    1. Creates multiple source repositories with GitHub Actions and smart contract files
    2. Creates an audit repository using the tool
    3. Verifies that:
       - GitHub Actions files are removed from all source repositories
       - Smart contract files from all repos are properly cloned
       - Branches and project boards are created correctly
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
    result = _create_audit_repo(config_path, github_token)

    assert result is True, "Audit repo creation should succeed"

    # Wait a bit for GitHub to propagate changes
    print("Waiting for GitHub to propagate changes...")
    time.sleep(5)

    # Get the GitHub client
    github = Github(github_token)

    # Get the target repo
    try:
        target_repo = github.get_organization(org_name).get_repo(target_repo_name)
        multi_repo_setup["test_repos"].append(target_repo)  # Add for cleanup

        # Verify the target repo was created
        assert target_repo is not None, f"Target repo {target_repo_name} should exist"

        # Clone the target repo for detailed inspection
        target_repo_path = clone_repo_to_temp(target_repo.clone_url, github_token, temp_dir, full_clone=True)

        # Fetch all branches
        subprocess.run(["git", "fetch", "--all"], cwd=target_repo_path, check=True)

        # Check each source repo in the target
        for source in sources:
            subfolder = source["sub_folder"]

            # Make sure we have the latest changes
            subprocess.run(["git", "fetch", "--all"], cwd=target_repo_path, check=True)
            subprocess.run(["git", "pull", "origin", "main"], cwd=target_repo_path, check=True)

            # Checkout main branch where source-repo is expected to be
            subprocess.run(["git", "checkout", "main"], cwd=target_repo_path, check=True)

            # Check for the source repository
            source_in_target_path = os.path.join(target_repo_path, subfolder)
            assert os.path.exists(source_in_target_path), f"Source repo {subfolder} should be in the target repo"

            # 1. Check for GitHub Actions removal
            # Check specifically for the problematic files we know should be removed
            github_workflow_path = os.path.join(source_in_target_path, ".github", "workflows", "test.yml")

            assert not os.path.exists(github_workflow_path), f"GitHub workflow file still exists: {github_workflow_path}"

            # Extra check to verify no GitHub Actions files remain
            action_paths = get_all_github_action_paths(source_in_target_path)
            if action_paths:
                print(f"WARNING: Unexpected GitHub Actions files found in {subfolder}: {action_paths}")

            # 2. Verify smart contract files exist
            # Normalize path for logging
            contract_path = normalize_path(os.path.join(source_in_target_path, "contracts/SimpleStorage.sol"))

            # Use OS-native paths for existence check
            contract_os_path = os.path.join(source_in_target_path, "contracts", "SimpleStorage.sol")

            assert os.path.exists(contract_os_path), f"Smart contract file SimpleStorage.sol should exist in the target repo under {subfolder} at {contract_path}"

        # 3. Verify report branch exists
        branches = [branch.name for branch in target_repo.get_branches()]
        assert "report" in branches, "Report branch should be created"

        # 4. Verify the workflow files in report generator
        # Checkout the report branch before checking for files
        subprocess.run(["git", "checkout", "report"], cwd=target_repo_path, check=True)

        # Add a short delay to ensure file system is fully updated
        time.sleep(2)

        report_generator_path = os.path.join(target_repo_path, "cyfrin-report", "report-generator-template")
        assert os.path.exists(report_generator_path), "Report generator template should be added as a subtree"

        # Check GitHub Actions in the Cyfrin report generator subtree
        if os.path.exists(report_generator_path):
            # The report generator might have legitimate GitHub Actions - we don't remove those
            actions_paths = get_all_github_action_paths(report_generator_path)
            print(f"Report generator actions (these should remain): {actions_paths}")

        # 5. Verify project board creation using GraphQL approach
        # This avoids the deprecated GitHub Projects Classic API
        project_title = multi_repo_setup["config"]["projectTitle"]
        assert verify_project_exists(github_token, org_name, project_title), f"A project with title containing '{project_title}' should exist"

    finally:
        # Cleanup is handled by the fixture
        pass
