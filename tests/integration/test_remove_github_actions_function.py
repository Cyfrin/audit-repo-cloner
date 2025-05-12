"""
Unit tests for the remove_github_actions function.
"""
import os
import tempfile

from audit_repo_cloner.create_audit_repo import remove_github_actions


def test_remove_github_actions_basic():
    """
    Test that remove_github_actions function properly removes .github/workflows directory.
    """
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a .github/workflows directory with a test workflow
        workflows_dir = os.path.join(temp_dir, ".github", "workflows")
        os.makedirs(workflows_dir, exist_ok=True)

        # Create a test workflow file
        with open(os.path.join(workflows_dir, "test.yml"), "w") as f:
            f.write("name: Test Workflow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n")

        # Create another file outside of .github to ensure it's not removed
        os.makedirs(os.path.join(temp_dir, "src"), exist_ok=True)
        with open(os.path.join(temp_dir, "src", "test.py"), "w") as f:
            f.write("print('This should remain')")

        # Run the function
        remove_github_actions(temp_dir)

        # Check that the workflows directory is gone
        assert not os.path.exists(workflows_dir), "Workflows directory should be removed"

        # Check that the src directory still exists
        assert os.path.exists(os.path.join(temp_dir, "src")), "src directory should remain"
        assert os.path.exists(os.path.join(temp_dir, "src", "test.py")), "test.py should remain"


def test_remove_github_actions_complex():
    """
    Test that remove_github_actions function properly removes various GitHub Actions structures.
    """
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a more complex directory structure

        # 1. Standard .github/workflows
        workflows_dir = os.path.join(temp_dir, ".github", "workflows")
        os.makedirs(workflows_dir, exist_ok=True)
        with open(os.path.join(workflows_dir, "ci.yml"), "w") as f:
            f.write("name: CI\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n")

        # 2. Custom action in .github/actions
        actions_dir = os.path.join(temp_dir, ".github", "actions", "custom-action")
        os.makedirs(actions_dir, exist_ok=True)
        with open(os.path.join(actions_dir, "action.yml"), "w") as f:
            f.write("name: 'Custom Action'\nruns:\n  using: 'composite'\n  steps:\n    - run: echo 'Custom action'")

        # 3. GitHub directory with other content that should remain
        docs_dir = os.path.join(temp_dir, ".github", "ISSUE_TEMPLATE")
        os.makedirs(docs_dir, exist_ok=True)
        with open(os.path.join(docs_dir, "bug.md"), "w") as f:
            f.write("# Bug Report\n\n## Description\n\n")

        # 4. A nested directory that happens to have an action.yml but isn't an actual GitHub Action
        nested_dir = os.path.join(temp_dir, "src", "some-component", "configs")
        os.makedirs(nested_dir, exist_ok=True)
        with open(os.path.join(nested_dir, "action.yml"), "w") as f:
            f.write("# This is just a config file, not an actual GitHub Action\nconfig:\n  key: value")

        # Run the function
        remove_github_actions(temp_dir)

        # Check that the workflows directory is gone
        assert not os.path.exists(workflows_dir), "Workflows directory should be removed"

        # Check that the custom action directory is gone
        assert not os.path.exists(actions_dir), "Custom action directory should be removed"

        # Check that the ISSUE_TEMPLATE directory still exists (not an action)
        assert os.path.exists(docs_dir), "ISSUE_TEMPLATE directory should remain"

        # Check that the nested directory still exists with its file
        assert os.path.exists(nested_dir), "Nested directory should remain"
        assert os.path.exists(os.path.join(nested_dir, "action.yml")), "Nested action.yml should remain"


def test_remove_github_actions_nested():
    """
    Test that remove_github_actions function handles nested repositories correctly.
    """
    # Create a temporary directory structure
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a nested structure like we might find in a multi-repo setup
        # Main repo
        main_workflows_dir = os.path.join(temp_dir, ".github", "workflows")
        os.makedirs(main_workflows_dir, exist_ok=True)
        with open(os.path.join(main_workflows_dir, "main.yml"), "w") as f:
            f.write("name: Main Workflow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n")

        # Nested repo 1
        nested1_dir = os.path.join(temp_dir, "repo1")
        os.makedirs(nested1_dir, exist_ok=True)
        nested1_workflows_dir = os.path.join(nested1_dir, ".github", "workflows")
        os.makedirs(nested1_workflows_dir, exist_ok=True)
        with open(os.path.join(nested1_workflows_dir, "nested1.yml"), "w") as f:
            f.write("name: Nested1 Workflow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n")

        # Nested repo 2
        nested2_dir = os.path.join(temp_dir, "repo2")
        os.makedirs(nested2_dir, exist_ok=True)
        nested2_workflows_dir = os.path.join(nested2_dir, ".github", "workflows")
        os.makedirs(nested2_workflows_dir, exist_ok=True)
        with open(os.path.join(nested2_workflows_dir, "nested2.yml"), "w") as f:
            f.write("name: Nested2 Workflow\non: [push]\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v2\n")

        # Remove GitHub Actions from only one of the nested repos
        remove_github_actions(nested1_dir)

        # Check that only the specified nested repo had its workflows removed
        assert os.path.exists(main_workflows_dir), "Main workflows should remain"
        assert not os.path.exists(nested1_workflows_dir), "Nested1 workflows should be removed"
        assert os.path.exists(nested2_workflows_dir), "Nested2 workflows should remain"

        # Now remove the remaining ones
        remove_github_actions(temp_dir)

        # Check that all workflows are now removed
        assert not os.path.exists(main_workflows_dir), "Main workflows should now be removed"
        assert not os.path.exists(nested1_workflows_dir), "Nested1 workflows should still be removed"
        assert not os.path.exists(nested2_workflows_dir), "Nested2 workflows should now be removed"


def test_remove_github_actions_empty():
    """
    Test that remove_github_actions function handles directories without GitHub Actions gracefully.
    """
    # Create a temporary directory without any GitHub Actions
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create some other content
        os.makedirs(os.path.join(temp_dir, "src", "components"), exist_ok=True)
        with open(os.path.join(temp_dir, "src", "components", "test.js"), "w") as f:
            f.write("console.log('test');")

        # Run the function
        remove_github_actions(temp_dir)

        # Check that the other content still exists
        assert os.path.exists(os.path.join(temp_dir, "src", "components", "test.js")), "Other content should remain"
