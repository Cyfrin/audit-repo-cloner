from __future__ import annotations

import logging as log
import re
from enum import Enum
from typing import List, Optional
from urllib.parse import quote, urlparse, urlunparse


class SourcePlatform(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"


# CI-related paths to remove from source repos (security measure)
GITHUB_CI_PATHS = [
    ".github/workflows",
    ".github/actions",
    ".github/action",
]

GITLAB_CI_PATHS = [
    ".gitlab-ci.yml",
    ".gitlab",
]

ALL_CI_PATHS = GITHUB_CI_PATHS + GITLAB_CI_PATHS


KNOWN_GITLAB_HOSTS = {"gitlab.com"}


def detect_source_platform(url: str, extra_gitlab_hosts: Optional[List[str]] = None, source_type_override: Optional[str] = None) -> SourcePlatform:
    """Detect whether a source URL points to GitHub or GitLab.

    If source_type_override is provided and valid, it takes precedence over auto-detection.
    Auto-detection uses hostname matching: github.com -> GITHUB, gitlab.com or hostname
    containing "gitlab" -> GITLAB, hostname in extra_gitlab_hosts -> GITLAB.
    Defaults to GITHUB for backward compatibility.
    """
    if source_type_override:
        override_lower = source_type_override.strip().lower()
        if override_lower == "github":
            return SourcePlatform.GITHUB
        elif override_lower == "gitlab":
            return SourcePlatform.GITLAB
        else:
            log.warning(f"Invalid sourceType '{source_type_override}', falling back to auto-detection")

    parsed = urlparse(url)
    hostname = (parsed.hostname or "").lower()

    if hostname == "github.com":
        return SourcePlatform.GITHUB

    if hostname in KNOWN_GITLAB_HOSTS or "gitlab" in hostname:
        return SourcePlatform.GITLAB

    extra_hosts = {h.strip().lower() for h in (extra_gitlab_hosts or [])}
    if hostname in extra_hosts:
        return SourcePlatform.GITLAB

    return SourcePlatform.GITHUB


def clean_source_url(url: str) -> str:
    """Clean a source URL by removing .git suffix, trailing slashes, and tree/branch paths.

    Strips patterns from both GitHub and GitLab unconditionally since the patterns
    are unambiguous. GitLab's /-/tree/ pattern is stripped before GitHub's /tree/
    pattern to avoid mangling GitLab URLs.
    """
    url = url.rstrip("/")

    # Strip tree paths BEFORE .git so "repo.git/-/tree/main" -> "repo.git" -> "repo"
    # GitLab: /-/tree/{branch} -- must be stripped BEFORE GitHub pattern
    url = re.sub(r"/-/tree/[^/]+/?$", "", url)
    # GitHub: /tree/{branch}
    url = re.sub(r"/tree/[^/]+/?$", "", url)

    # Only strip trailing .git (not mid-string occurrences like "my.github.tools")
    url = re.sub(r"\.git$", "", url)

    return url


def make_authenticated_url(url: str, platform: SourcePlatform, github_token: str, gitlab_token: Optional[str] = None) -> str:
    """Inject the appropriate auth token into the source URL.

    Validates HTTPS scheme and URL-encodes tokens to handle special characters.
    """
    if not url.startswith("https://"):
        raise ValueError(f"Source URL must use HTTPS (got: {sanitize_url(url)}). Credentials over plaintext HTTP are a security risk.")

    if platform == SourcePlatform.GITHUB:
        encoded_token = quote(github_token, safe="")
        return url.replace("https://", f"https://{encoded_token}@")
    elif platform == SourcePlatform.GITLAB:
        if not gitlab_token:
            raise ValueError(f"GitLab source URL detected ({sanitize_url(url)}) but no GitLab token provided. Set GITLAB_ACCESS_TOKEN in .env or pass --gitlab-token.")
        encoded_token = quote(gitlab_token, safe="")
        return url.replace("https://", f"https://oauth2:{encoded_token}@")

    raise ValueError(f"Unsupported source platform: {platform}")


def sanitize_url(url: str) -> str:
    """Strip embedded credentials from a URL for safe logging/error messages."""
    try:
        parsed = urlparse(url)
        if parsed.username or parsed.password:
            # Replace userinfo with ***
            sanitized = parsed._replace(netloc=f"***@{parsed.hostname}" + (f":{parsed.port}" if parsed.port else ""))
            return urlunparse(sanitized)
    except Exception:
        pass
    return url


def validate_tokens_for_repos(repositories: List[dict], github_token: str, gitlab_token: Optional[str] = None, extra_gitlab_hosts: Optional[List[str]] = None) -> None:
    """Validate that required tokens are available for all source repositories.

    Scans all sourceUrls upfront and raises a clear error if any GitLab URL
    is found without a GitLab token. Call this before creating the target repo
    to avoid partial state.
    """
    gitlab_repos = []
    for repo_config in repositories:
        source_url = repo_config.get("sourceUrl", "")
        if not source_url:
            continue
        source_type_override = repo_config.get("sourceType")
        platform = detect_source_platform(source_url, extra_gitlab_hosts, source_type_override)
        if platform == SourcePlatform.GITLAB:
            gitlab_repos.append(source_url)

    if gitlab_repos and not gitlab_token:
        urls = "\n  ".join(gitlab_repos)
        raise ValueError(f"GitLab source repositories detected but no GitLab token provided:\n  {urls}\nSet GITLAB_ACCESS_TOKEN in .env or pass --gitlab-token.")
