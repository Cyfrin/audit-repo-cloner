# Integration Tests

This directory contains integration tests for the audit-repo-cloner tool.

## Prerequisites

To run the integration tests, you need:

1. A GitHub account with access to an organization where you can create temporary repositories
2. A GitHub personal access token with appropriate permissions (repo, workflow, delete_repo)
3. Python with pytest installed

## Environment Setup

The integration tests require the following environment variables:

```bash
TEST_GITHUB_TOKEN=your_github_token
TEST_GITHUB_ORG=your_organization_name
```

There are three ways to set these variables:

1. **Environment Variables**: Set them directly in your shell:
   ```bash
   export TEST_GITHUB_TOKEN=your_github_token
   export TEST_GITHUB_ORG=your_organization_name
   ```

2. **Using a .env file**: Create a `.env` file at the root of the repository:
   ```
   TEST_GITHUB_TOKEN=your_github_token
   TEST_GITHUB_ORG=your_organization_name
   ```

3. **Using a specific testing .env file**: Create one of these files at the root:
   ```
   .env.test
   .env.local
   ```

The tests will automatically check for these files in the order: `.env`, `.env.test`, `.env.local`.

## Running Tests

To run all tests:

```bash
pytest -xvs tests/
```

To run only the integration tests:

```bash
pytest -xvs tests/integration/
```

To run a specific test file:

```bash
pytest -xvs tests/integration/test_github_actions_removal.py
```

To run the smart contract repository tests:

```bash
pytest -xvs tests/integration/test_smart_contract_repo_cloning.py
```

## Utility Scripts

### Cleanup Test Repositories

This directory contains a utility script to clean up stale test repositories that might have been created during test runs:

```bash
# Clean up test repos created in the last 3 hours (default)
python tests/cleanup_test_repos.py

# Clean up test repos created in the last 6 hours
python tests/cleanup_test_repos.py --hours 6

# Dry run mode (show what would be deleted without actually deleting)
python tests/cleanup_test_repos.py --dry-run
```

The cleanup script will look for repositories matching patterns like `audit-repo-*`, `source-repo-*`, etc., and delete them if they were created within the specified time window.

## Test Structure

The integration tests are designed to:

1. Create temporary GitHub repositories for testing
2. Run the audit repo cloner on those repositories
3. Verify the results
4. Clean up all created repositories

The tests utilize fixtures defined in `conftest.py` to set up and tear down the test environment.

### Smart Contract Repository Tests

The `test_smart_contract_repo_cloning.py` file contains tests that specifically check the audit tool's functionality with smart contract repositories:

1. `test_single_smart_contract_repo_cloning` - Tests cloning a single repository with Solidity contracts
2. `test_multi_smart_contract_repo_cloning` - Tests cloning multiple repositories with Solidity contracts
3. `test_branch_generation` - Verifies the creation of branches for auditors and the report
4. `test_report_workflow_generation` - Checks that the report branch and workflows are properly set up
5. `test_project_board_generation` - Validates the creation of the project board with the correct columns

These tests create sample Solidity contract files and Hardhat configurations to simulate real smart contract repositories.

## Warning

These tests create and delete real repositories in your GitHub organization. While they attempt to clean up after themselves, ensure you have the appropriate permissions and are using a testing organization, not your production environment.

Also, note that the tests may take some time to run since they involve creating actual GitHub repositories and cloning them.

## Notes for Contributors

When adding new integration tests:

1. Use the existing fixtures when possible
2. Always ensure proper cleanup in a finally block
3. Add appropriate assertions to verify the behavior
4. Name test functions descriptively (e.g., `test_github_actions_removal`)
5. Consider using parametrized tests for testing multiple variations