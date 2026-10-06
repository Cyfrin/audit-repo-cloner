from __future__ import annotations

import json
import logging as log
from typing import Dict, List

from github import Github, GithubException, Repository

from audit_repo_cloner.github_project_utils import add_team_to_project

# auditors.json in report-generator-template is the single source of truth for valid auditors
AUDITORS_JSON_REPO = "Cyfrin/report-generator-template"
AUDITORS_JSON_PATH = "source/auditors.json"
AUDITORS_JSON_REF = "main"

AUDITORS_TEAM_SLUG = "auditors"
AUDITORS_TEAM_PERMISSION = "admin"
AUDITORS_TEAM_PROJECT_ROLE = "ADMIN"
EXTERNAL_AUDITOR_PERMISSION = "push"  # "Write" in the GitHub UI

FORMAL_VERIFICATION_SUFFIX = "Formal Verification"
MANUAL_REVIEW = "Manual Review"


def fetch_auditor_mapping(github: Github) -> Dict[str, dict]:
    contents = github.get_repo(AUDITORS_JSON_REPO).get_contents(AUDITORS_JSON_PATH, ref=AUDITORS_JSON_REF)
    return json.loads(contents.decoded_content)


def _individual_names(auditors: List[str], mapping: Dict[str, dict]) -> List[str]:
    """Expands team entries (those with "members") into their individual members."""
    names = []
    for auditor in auditors:
        for name in mapping[auditor].get("members", [auditor]):
            if name not in names:
                names.append(name)
    return names


def validate_auditors(auditors: List[str], mapping: Dict[str, dict]) -> None:
    unknown = [auditor for auditor in auditors if auditor not in mapping]
    if unknown:
        raise ValueError(f"Unknown auditor(s) {unknown}; names must match an entry in {AUDITORS_JSON_REPO}/{AUDITORS_JSON_PATH} (case-sensitive).")

    unknown_members = [f"{auditor} -> {member}" for auditor in auditors for member in mapping[auditor].get("members", []) if member not in mapping]
    if unknown_members:
        raise ValueError(f"Team member(s) missing from {AUDITORS_JSON_PATH}: {unknown_members}")


def resolve_github_handles(auditors: List[str], mapping: Dict[str, dict]) -> List[str]:
    """Returns the GitHub usernames of every auditor, with teams expanded into their members."""
    names = _individual_names(auditors, mapping)
    missing = [name for name in names if not (mapping[name].get("github") or "").strip()]
    if missing:
        raise ValueError(f"Auditor(s) {missing} have no 'github' username in {AUDITORS_JSON_REPO}/{AUDITORS_JSON_PATH}; add it so they can be given access to the audit repo.")
    return [mapping[name]["github"].strip() for name in names]


def get_review_methods(auditors: List[str], mapping: Dict[str, dict]) -> str:
    names = list(auditors) + _individual_names(auditors, mapping)
    if any(mapping[name].get("suffix") == FORMAL_VERIFICATION_SUFFIX for name in names):
        return f"{MANUAL_REVIEW}, {FORMAL_VERIFICATION_SUFFIX}"
    return MANUAL_REVIEW


def verify_github_users_exist(github: Github, handles: List[str]) -> None:
    missing = []
    for handle in handles:
        try:
            github.get_user(handle).id
        except GithubException:
            missing.append(handle)
    if missing:
        raise ValueError(f"GitHub user(s) {missing} not found; check the 'github' usernames in {AUDITORS_JSON_REPO}/{AUDITORS_JSON_PATH}.")


def grant_repo_access(github: Github, organization: str, repo: Repository, handles: List[str], github_token: str, project_id: str = None) -> None:
    """Gives the auditors team admin access to the repo and project board, and invites any auditor outside that team to the repo with write access."""
    team = github.get_organization(organization).get_team_by_slug(AUDITORS_TEAM_SLUG)
    team.update_team_repository(repo, AUDITORS_TEAM_PERMISSION)
    print(f"Gave {organization}/{AUDITORS_TEAM_SLUG} {AUDITORS_TEAM_PERMISSION} access to {repo.name}")

    if project_id:
        try:
            add_team_to_project(github_token, project_id, team.node_id, AUDITORS_TEAM_PROJECT_ROLE)
            print(f"Gave {organization}/{AUDITORS_TEAM_SLUG} admin access to the project board")
        except Exception as e:
            log.error(f"{e}\nThe token needs the read:org scope to add {organization}/{AUDITORS_TEAM_SLUG} to the project board; please add it manually.")

    team_members = {member.login.lower() for member in team.get_members()}
    for handle in handles:
        if handle.lower() in team_members:
            print(f"{handle} is in {organization}/{AUDITORS_TEAM_SLUG}; no invite needed")
            continue
        try:
            repo.add_to_collaborators(handle, permission=EXTERNAL_AUDITOR_PERMISSION)
            print(f"Invited {handle} to {repo.name} with write access")
        except GithubException as e:
            log.error(f"Failed to invite {handle} to {repo.name}: {e}")
