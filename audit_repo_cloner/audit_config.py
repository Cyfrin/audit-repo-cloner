from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import date
from typing import List

DEFAULT_SCOPE_FILE = "scope.md"

# Fixed English month names; strftime("%b") depends on the system locale
MONTH_ABBREVIATIONS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")

# Fields which used to be specified manually but are now derived from teamName/projectName/startDate
LEGACY_FIELDS = ("targetRepoName", "projectTitle")


@dataclass
class AuditConfig:
    team_name: str
    project_name: str
    team_website: str
    start_date: date
    end_date: date
    scope_markdown: str
    auditors: List[str]
    repositories: List[dict]

    @property
    def title_text(self) -> str:
        return build_title_text(self.team_name, self.project_name)

    @property
    def year_month(self) -> str:
        return self.start_date.strftime("%Y-%m")

    @property
    def target_repo_name(self) -> str:
        return f"audit-{self.year_month}-{slugify(self.title_text)}"

    @property
    def project_title(self) -> str:
        return f"[Audit] {self.title_text} ({self.year_month})"

    @property
    def review_timeline(self) -> str:
        return format_review_timeline(self.start_date, self.end_date)


def build_title_text(team_name: str, project_name: str) -> str:
    """Mirrors build_title_text() in report-generator-template/scripts/helpers.py; keep them in sync
    so the repo name, project board title and report title/filenames all agree."""
    if team_name.lower() in project_name.lower():
        return project_name
    return team_name + " " + project_name


def slugify(text: str) -> str:
    """Mirrors slugify() in report-generator-template/scripts/helpers.py"""
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def ordinal(day: int) -> str:
    if 11 <= day % 100 <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{day}{suffix}"


def format_review_timeline(start: date, end: date) -> str:
    """Formats dates as expected by summary_information.conf, e.g. "Oct 4th - Oct 5th, 2026".

    The report generator's calculate_period() splits on " - " so both sides are always emitted.
    """
    start_text = f"{MONTH_ABBREVIATIONS[start.month - 1]} {ordinal(start.day)}"
    end_text = f"{MONTH_ABBREVIATIONS[end.month - 1]} {ordinal(end.day)}, {end.year}"
    if start.year != end.year:
        start_text += f", {start.year}"
    return f"{start_text} - {end_text}"


def _required_string(config: dict, key: str) -> str:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"'{key}' must be provided in the config file.")
    value = value.strip()
    if "\n" in value:
        raise ValueError(f"'{key}' must be a single line.")
    return value


def _required_date(config: dict, key: str) -> date:
    value = _required_string(config, key)
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"'{key}' must be an ISO date (YYYY-MM-DD), got '{value}'.")


def parse_audit_config(config: dict, config_dir: str) -> AuditConfig:
    """Validates the raw config.json contents; raises ValueError describing the first problem found."""
    legacy = [field for field in LEGACY_FIELDS if field in config]
    if legacy:
        raise ValueError(f"{', '.join(legacy)} are no longer supported; the repo name and project board title are derived from teamName, projectName and startDate. Please remove them from the config file.")

    team_name = _required_string(config, "teamName")
    project_name = _required_string(config, "projectName")

    team_website = _required_string(config, "teamWebsite")
    if not team_website.startswith(("https://", "http://")):
        raise ValueError(f"'teamWebsite' must be a full URL starting with https://, got '{team_website}'.")

    start_date = _required_date(config, "startDate")
    end_date = _required_date(config, "endDate")
    if end_date < start_date:
        raise ValueError(f"'endDate' ({end_date}) is before 'startDate' ({start_date}).")

    auditors = (config.get("auditors") or "").split()
    if not auditors:
        raise ValueError("'auditors' must be provided in the config file.")

    repositories = config.get("repositories") or []
    if not repositories:
        raise ValueError("No repositories specified in the config file.")

    scope_file = config.get("scopeFile") or DEFAULT_SCOPE_FILE
    scope_path = scope_file if os.path.isabs(scope_file) else os.path.join(config_dir, scope_file)
    if not os.path.isfile(scope_path):
        raise ValueError(f"Scope file '{scope_path}' not found. Create it with the markdown for audit_scope.md, or set 'scopeFile' in the config file.")
    with open(scope_path, "r") as f:
        scope_markdown = f.read()
    if not scope_markdown.strip():
        raise ValueError(f"Scope file '{scope_path}' is empty.")

    audit_config = AuditConfig(
        team_name=team_name,
        project_name=project_name,
        team_website=team_website,
        start_date=start_date,
        end_date=end_date,
        scope_markdown=scope_markdown,
        auditors=auditors,
        repositories=repositories,
    )
    if not slugify(audit_config.title_text):
        raise ValueError("teamName/projectName must contain at least one letter or digit.")
    return audit_config


def load_audit_config(config_file: str) -> AuditConfig:
    with open(config_file, "r") as f:
        config = json.load(f)
    return parse_audit_config(config, os.path.dirname(os.path.abspath(config_file)))
