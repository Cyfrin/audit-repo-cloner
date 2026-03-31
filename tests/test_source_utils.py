from __future__ import annotations

import pytest

from audit_repo_cloner.source_utils import ALL_CI_PATHS, GITHUB_CI_PATHS, GITLAB_CI_PATHS, SourcePlatform, clean_source_url, detect_source_platform, make_authenticated_url, sanitize_url, validate_tokens_for_repos

# --- detect_source_platform ---


class TestDetectSourcePlatform:
    def test_github_com(self):
        assert detect_source_platform("https://github.com/user/repo") == SourcePlatform.GITHUB

    def test_gitlab_com(self):
        assert detect_source_platform("https://gitlab.com/group/repo") == SourcePlatform.GITLAB

    def test_hostname_contains_gitlab(self):
        assert detect_source_platform("https://gitlab.mycompany.com/group/repo") == SourcePlatform.GITLAB

    def test_hostname_contains_gitlab_prefix(self):
        assert detect_source_platform("https://my-gitlab.corp.net/group/repo") == SourcePlatform.GITLAB

    def test_extra_gitlab_hosts(self):
        assert detect_source_platform("https://git.internal.io/group/repo", extra_gitlab_hosts=["git.internal.io"]) == SourcePlatform.GITLAB

    def test_unknown_defaults_to_github(self):
        assert detect_source_platform("https://git.internal.io/group/repo") == SourcePlatform.GITHUB

    def test_case_insensitive_hostname(self):
        assert detect_source_platform("https://GitLab.com/group/repo") == SourcePlatform.GITLAB
        assert detect_source_platform("https://GITHUB.COM/user/repo") == SourcePlatform.GITHUB

    def test_case_insensitive_extra_hosts(self):
        assert detect_source_platform("https://GIT.INTERNAL.IO/group/repo", extra_gitlab_hosts=["git.internal.io"]) == SourcePlatform.GITLAB

    def test_source_type_override_github(self):
        assert detect_source_platform("https://gitlab.com/group/repo", source_type_override="github") == SourcePlatform.GITHUB

    def test_source_type_override_gitlab(self):
        assert detect_source_platform("https://github.com/user/repo", source_type_override="gitlab") == SourcePlatform.GITLAB

    def test_source_type_override_case_insensitive(self):
        assert detect_source_platform("https://example.com/repo", source_type_override="GitLab") == SourcePlatform.GITLAB
        assert detect_source_platform("https://example.com/repo", source_type_override="GITHUB") == SourcePlatform.GITHUB

    def test_source_type_override_invalid_falls_back(self):
        # Invalid override falls back to auto-detection
        assert detect_source_platform("https://github.com/user/repo", source_type_override="bitbucket") == SourcePlatform.GITHUB
        assert detect_source_platform("https://gitlab.com/group/repo", source_type_override="invalid") == SourcePlatform.GITLAB


# --- clean_source_url ---


class TestCleanSourceUrl:
    def test_strips_trailing_dot_git(self):
        assert clean_source_url("https://github.com/user/repo.git") == "https://github.com/user/repo"

    def test_preserves_mid_string_dot_git(self):
        assert clean_source_url("https://gitlab.com/org/my.github.tools") == "https://gitlab.com/org/my.github.tools"

    def test_strips_trailing_slash(self):
        assert clean_source_url("https://github.com/user/repo/") == "https://github.com/user/repo"

    def test_strips_github_tree_branch(self):
        assert clean_source_url("https://github.com/user/repo/tree/main") == "https://github.com/user/repo"

    def test_strips_github_tree_branch_with_trailing_slash(self):
        assert clean_source_url("https://github.com/user/repo/tree/main/") == "https://github.com/user/repo"

    def test_strips_gitlab_tree_branch(self):
        assert clean_source_url("https://gitlab.com/group/repo/-/tree/develop") == "https://gitlab.com/group/repo"

    def test_strips_gitlab_tree_branch_with_trailing_slash(self):
        assert clean_source_url("https://gitlab.com/group/repo/-/tree/develop/") == "https://gitlab.com/group/repo"

    def test_already_clean_url_unchanged(self):
        assert clean_source_url("https://github.com/user/repo") == "https://github.com/user/repo"

    def test_combined_dot_git_and_github_tree(self):
        assert clean_source_url("https://github.com/user/repo/tree/main") == "https://github.com/user/repo"

    def test_combined_dot_git_and_gitlab_tree(self):
        """Regression: repo.git/-/tree/main should strip both tree path and .git"""
        assert clean_source_url("https://gitlab.com/group/repo.git/-/tree/main") == "https://gitlab.com/group/repo"

    def test_combined_dot_git_and_github_tree_with_git_suffix(self):
        assert clean_source_url("https://github.com/user/repo.git/tree/main") == "https://github.com/user/repo"

    def test_gitlab_subgroups(self):
        assert clean_source_url("https://gitlab.com/group/subgroup/subsubgroup/repo.git") == "https://gitlab.com/group/subgroup/subsubgroup/repo"

    def test_gitlab_tree_not_mangled_by_github_pattern(self):
        """Regression: GitLab /-/tree/ must be stripped before GitHub /tree/ pattern"""
        assert clean_source_url("https://gitlab.com/group/repo/-/tree/main") == "https://gitlab.com/group/repo"


# --- make_authenticated_url ---


class TestMakeAuthenticatedUrl:
    def test_github_auth(self):
        result = make_authenticated_url("https://github.com/user/repo", SourcePlatform.GITHUB, "ghp_token123", None)
        assert result == "https://ghp_token123@github.com/user/repo"

    def test_gitlab_auth(self):
        result = make_authenticated_url("https://gitlab.com/group/repo", SourcePlatform.GITLAB, "ghp_token", "glpat-abc123")
        assert result == "https://oauth2:glpat-abc123@gitlab.com/group/repo"

    def test_gitlab_missing_token_raises(self):
        with pytest.raises(ValueError, match="no GitLab token provided"):
            make_authenticated_url("https://gitlab.com/group/repo", SourcePlatform.GITLAB, "ghp_token", None)

    def test_http_url_raises(self):
        with pytest.raises(ValueError, match="must use HTTPS"):
            make_authenticated_url("http://github.com/user/repo", SourcePlatform.GITHUB, "token", None)

    def test_url_encodes_special_characters_github(self):
        result = make_authenticated_url("https://github.com/user/repo", SourcePlatform.GITHUB, "tok@n/with#special%chars", None)
        assert "tok%40n%2Fwith%23special%25chars@github.com" in result

    def test_url_encodes_special_characters_gitlab(self):
        result = make_authenticated_url("https://gitlab.com/group/repo", SourcePlatform.GITLAB, "ghp", "gl@pat/tok#en")
        assert "oauth2:gl%40pat%2Ftok%23en@gitlab.com" in result


# --- sanitize_url ---


class TestSanitizeUrl:
    def test_strips_user_password(self):
        result = sanitize_url("https://oauth2:glpat-secret@gitlab.com/group/repo")
        assert "glpat-secret" not in result
        assert "gitlab.com" in result

    def test_strips_token_only(self):
        result = sanitize_url("https://ghp_token123@github.com/user/repo")
        assert "ghp_token123" not in result
        assert "github.com" in result

    def test_clean_url_unchanged(self):
        url = "https://github.com/user/repo"
        assert sanitize_url(url) == url

    def test_preserves_port(self):
        result = sanitize_url("https://user:pass@gitlab.example.com:8443/group/repo")
        assert "pass" not in result
        assert "8443" in result

    def test_strips_url_encoded_credentials(self):
        result = sanitize_url("https://tok%40en@github.com/user/repo")
        assert "tok%40en" not in result
        assert "github.com" in result
        assert "/user/repo" in result


# --- validate_tokens_for_repos ---


class TestValidateTokensForRepos:
    def test_github_only_no_gitlab_token_ok(self):
        repos = [{"sourceUrl": "https://github.com/user/repo", "commitHash": "abc"}]
        validate_tokens_for_repos(repos, "ghp_token", None)

    def test_gitlab_with_token_ok(self):
        repos = [{"sourceUrl": "https://gitlab.com/group/repo", "commitHash": "abc"}]
        validate_tokens_for_repos(repos, "ghp_token", "glpat-token")

    def test_gitlab_without_token_raises(self):
        repos = [{"sourceUrl": "https://gitlab.com/group/repo", "commitHash": "abc"}]
        with pytest.raises(ValueError, match="no GitLab token provided"):
            validate_tokens_for_repos(repos, "ghp_token", None)

    def test_mixed_repos_without_gitlab_token_raises(self):
        repos = [
            {"sourceUrl": "https://github.com/user/repo", "commitHash": "abc"},
            {"sourceUrl": "https://gitlab.com/group/repo", "commitHash": "def"},
        ]
        with pytest.raises(ValueError, match="no GitLab token provided"):
            validate_tokens_for_repos(repos, "ghp_token", None)

    def test_mixed_repos_with_tokens_ok(self):
        repos = [
            {"sourceUrl": "https://github.com/user/repo", "commitHash": "abc"},
            {"sourceUrl": "https://gitlab.com/group/repo", "commitHash": "def"},
        ]
        validate_tokens_for_repos(repos, "ghp_token", "glpat-token")

    def test_respects_source_type_override(self):
        repos = [{"sourceUrl": "https://custom.host.com/group/repo", "commitHash": "abc", "sourceType": "gitlab"}]
        with pytest.raises(ValueError, match="no GitLab token provided"):
            validate_tokens_for_repos(repos, "ghp_token", None)

    def test_extra_gitlab_hosts(self):
        repos = [{"sourceUrl": "https://git.internal.io/group/repo", "commitHash": "abc"}]
        with pytest.raises(ValueError, match="no GitLab token provided"):
            validate_tokens_for_repos(repos, "ghp_token", None, extra_gitlab_hosts=["git.internal.io"])

    def test_skips_empty_source_url(self):
        repos = [{"sourceUrl": "", "commitHash": "abc"}]
        validate_tokens_for_repos(repos, "ghp_token", None)

    def test_empty_repos_list(self):
        validate_tokens_for_repos([], "ghp_token", None)


# --- CI path constants ---


class TestCIPathConstants:
    def test_github_ci_paths(self):
        assert ".github/workflows" in GITHUB_CI_PATHS
        assert ".github/actions" in GITHUB_CI_PATHS

    def test_gitlab_ci_paths(self):
        assert ".gitlab-ci.yml" in GITLAB_CI_PATHS
        assert ".gitlab" in GITLAB_CI_PATHS

    def test_all_ci_paths_contains_both(self):
        for path in GITHUB_CI_PATHS:
            assert path in ALL_CI_PATHS
        for path in GITLAB_CI_PATHS:
            assert path in ALL_CI_PATHS
