"""
Integration tests for audit repository cloning functionality.
This file contains all GitHub integration tests for the audit-repo-cloner tool.
Tests include repository creation, GitHub Actions removal, multi-repository cloning,
branch setup, and project board configuration.
"""
import os
import re
import subprocess

from github import Github

from audit_repo_cloner.create_audit_repo import _create_audit_repo
from tests.integration.test_utils import check_file_exists, check_git_history, clone_repo_to_temp, get_all_github_action_paths, normalize_path


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

    # Add a simple smart contract to the source repo if it doesn't exist
    if not check_file_exists(source_repo, "SimpleStorage.sol"):
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
        source_repo.create_file("SimpleStorage.sol", "Add smart contract", solidity_code)

    # Run the audit repo cloner
    print("Running the audit repo cloner...")
    result = _create_audit_repo(config_path, github_token)

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

        # 1. Check that source repo has been cloned to the expected location
        source_in_target_path = os.path.join(target_repo_path, "source-repo")
        assert os.path.exists(source_in_target_path), "Source repo should be in the target repo"

        # 2. Verify GitHub Actions removal
        action_paths = get_all_github_action_paths(source_in_target_path)
        assert len(action_paths) == 0, f"Found GitHub Actions files in source repo subtree: {action_paths}"

        # 3. Verify smart contract files exist
        solidity_file_found = False
        for root, dirs, files in os.walk(source_in_target_path):
            for file in files:
                if file == "SimpleStorage.sol":
                    solidity_file_found = True
                    print(f"Found SimpleStorage.sol at {os.path.relpath(os.path.join(root, file), target_repo_path)}")

        assert solidity_file_found, "SimpleStorage.sol file not found in the target repo"

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

        # Verify report generator template is present
        report_generator_path = os.path.join(target_repo_path, "report-generator-template")
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

        # 6. Check project board
        projects = list(target_repo.get_projects())
        assert len(projects) > 0, "At least one project board should be created"

        # Find project with matching title
        project = None
        for p in projects:
            if project_title in p.name:
                project = p
                break

        assert project is not None, f"A project with title containing '{project_title}' should exist"

        # Check for expected columns
        columns = list(project.get_columns())
        column_names = [column.name for column in columns]

        expected_columns = ["To Do", "In Progress", "Done"]
        for expected_column in expected_columns:
            found = False
            for column_name in column_names:
                if expected_column.lower() in column_name.lower():
                    found = True
                    break
            assert found, f"Project should have a column similar to '{expected_column}'"

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

            # 1. Check for GitHub Actions removal
            action_paths = get_all_github_action_paths(source_in_target_path)
            assert len(action_paths) == 0, f"Found GitHub Actions files in {subfolder}: {action_paths}"

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
        report_generator_path = os.path.join(target_repo_path, "report-generator-template")
        assert os.path.exists(report_generator_path), "Report generator template should be added as a subtree"

        # Check GitHub Actions in the Cyfrin report generator subtree
        if os.path.exists(report_generator_path):
            # The report generator might have legitimate GitHub Actions - we don't remove those
            actions_paths = get_all_github_action_paths(report_generator_path)
            print(f"Report generator actions (these should remain): {actions_paths}")

        # 5. Verify project board creation
        projects = list(target_repo.get_projects())
        assert len(projects) > 0, "At least one project board should be created"

    finally:
        # Cleanup is handled by the fixture
        pass
