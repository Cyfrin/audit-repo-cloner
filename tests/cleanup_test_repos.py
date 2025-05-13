#!/usr/bin/env python
"""
Script to clean up stale test repositories in the GitHub organization.
Removes repositories with name patterns like 'audit-repo-*' and 'source-repo-*'
that were created within a specified time window.
"""
import argparse
import os
import re
import sys
from datetime import datetime, timedelta, timezone

from dotenv import load_dotenv
from github import Github, GithubException


def load_env_files():
    """Load environment variables from .env files."""
    # Try loading from various env files in order of preference
    env_files = [".env", ".env.test", ".env.local"]

    # Look in the repository root
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    for env_file in env_files:
        env_path = os.path.join(repo_root, env_file)
        if os.path.exists(env_path):
            load_dotenv(env_path)
            print(f"Loaded environment from {env_path}")
            return True

    return False


def cleanup_test_repos(hours=3, dry_run=False):
    """
    Clean up test repositories created within the specified hours.

    Args:
        hours: Number of hours to look back for repository creation
        dry_run: If True, only print repositories that would be deleted without actually deleting them
    """
    github_token = os.environ.get("TEST_GITHUB_TOKEN")
    if not github_token:
        print("ERROR: TEST_GITHUB_TOKEN environment variable not set")
        sys.exit(1)

    org_name = os.environ.get("TEST_GITHUB_ORG")
    if not org_name:
        print("ERROR: TEST_GITHUB_ORG environment variable not set")
        sys.exit(1)

    # Create GitHub client
    g = Github(github_token)

    try:
        # Get the GitHub organization
        org = g.get_organization(org_name)

        # Calculate the cutoff time in UTC (GitHub API uses UTC timestamps)
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=hours)

        # Get all repositories in the organization
        repos = org.get_repos()

        # Define regex patterns to match our test repo naming convention
        # Matches test repository naming patterns with various length hex suffixes
        repo_patterns = [re.compile(r"^audit-repo-[0-9a-f]+$"), re.compile(r"^source-repo-[0-9a-f]+$"), re.compile(r"^source-repo-\d+-[0-9a-f]+$"), re.compile(r"^multi-audit-repo-[0-9a-f]+$")]

        # Track statistics
        total_repos = 0
        eligible_repos = 0
        deleted_repos = 0
        failed_repos = 0

        print(f"Scanning repositories in organization {org_name} created in the last {hours} hours...")

        # Process each repository
        for repo in repos:
            total_repos += 1

            # Check if the repo name matches one of our test patterns
            is_test_repo = any(pattern.match(repo.name) for pattern in repo_patterns)

            # Make sure created_at has timezone info (the GitHub API may return offset-naive datetimes)
            repo_created_at = repo.created_at
            if repo_created_at.tzinfo is None:
                repo_created_at = repo_created_at.replace(tzinfo=timezone.utc)

            # Check if the repo was created within the specified time window
            is_recent = repo_created_at > cutoff_time

            # Display with timezone info for debugging
            datetime.now()
            datetime.now(timezone.utc)

            if is_test_repo and is_recent:
                eligible_repos += 1
                print(f"Found eligible test repository: {repo.name} (created at {repo_created_at})")

                if not dry_run:
                    try:
                        print(f"Deleting repository: {repo.name}")
                        repo.delete()
                        deleted_repos += 1
                        print(f"Successfully deleted {repo.name}")
                    except GithubException as e:
                        failed_repos += 1
                        print(f"Error deleting repository {repo.name}: {e}")

        # Print summary
        print("\nCleanup Summary:")
        print(f"Total repositories scanned: {total_repos}")
        print(f"Eligible test repositories found: {eligible_repos}")

        if dry_run:
            print(f"Dry run mode: {eligible_repos} repositories would be deleted")
        else:
            print(f"Repositories successfully deleted: {deleted_repos}")
            print(f"Repositories failed to delete: {failed_repos}")

    except Exception as e:
        print(f"Error during cleanup: {e}")
        sys.exit(1)


def main():
    """Parse command line arguments and run the cleanup."""
    parser = argparse.ArgumentParser(description="Clean up stale test repositories in GitHub organization")
    parser.add_argument("--hours", type=int, default=3, help="Delete repositories created within this many hours (default: 3)")
    parser.add_argument("--dry-run", action="store_true", help="List repositories that would be deleted without actually deleting them")

    args = parser.parse_args()

    # Load environment variables
    if not load_env_files():
        print("Warning: No .env file found. Make sure environment variables are set.")

    # Run cleanup
    cleanup_test_repos(hours=args.hours, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
