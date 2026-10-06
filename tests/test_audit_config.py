from __future__ import annotations

from datetime import date

import pytest

from audit_repo_cloner.audit_config import build_title_text, format_review_timeline, ordinal, parse_audit_config, slugify

# --- build_title_text / slugify ---


class TestBuildTitleText:
    def test_distinct_team_and_project_are_joined(self):
        assert build_title_text("Securitize", "Tempo Async Vault") == "Securitize Tempo Async Vault"

    def test_team_contained_in_project_is_not_repeated(self):
        assert build_title_text("Aztec", "Aztec Polynomial") == "Aztec Polynomial"

    def test_identical_names(self):
        assert build_title_text("Linea", "Linea") == "Linea"

    def test_containment_is_case_insensitive(self):
        assert build_title_text("greekfi", "GreekFi Oracle") == "GreekFi Oracle"


class TestSlugify:
    def test_basic(self):
        assert slugify("Securitize Tempo Async Vault") == "securitize-tempo-async-vault"

    def test_collapses_punctuation_and_trims(self):
        assert slugify("  Note Systems: Frontend (v2)! ") == "note-systems-frontend-v2"


# --- review timeline ---


class TestOrdinal:
    @pytest.mark.parametrize("day,expected", [(1, "1st"), (2, "2nd"), (3, "3rd"), (4, "4th"), (11, "11th"), (12, "12th"), (13, "13th"), (21, "21st"), (22, "22nd"), (23, "23rd"), (31, "31st")])
    def test_suffixes(self, day, expected):
        assert ordinal(day) == expected


class TestFormatReviewTimeline:
    def test_same_year(self):
        assert format_review_timeline(date(2026, 10, 4), date(2026, 10, 5)) == "Oct 4th - Oct 5th, 2026"

    def test_across_months(self):
        assert format_review_timeline(date(2026, 9, 28), date(2026, 10, 2)) == "Sep 28th - Oct 2nd, 2026"

    def test_across_years_includes_both_years(self):
        assert format_review_timeline(date(2026, 12, 28), date(2027, 1, 3)) == "Dec 28th, 2026 - Jan 3rd, 2027"

    def test_single_day_still_has_both_sides(self):
        assert format_review_timeline(date(2026, 10, 4), date(2026, 10, 4)) == "Oct 4th - Oct 4th, 2026"


# --- parse_audit_config ---


@pytest.fixture
def config_dir(tmp_path):
    (tmp_path / "scope.md").write_text("The audit scope was limited to:\n```\nsrc/Vault.sol\n```")
    return str(tmp_path)


def make_config(**overrides):
    config = {
        "teamName": "Securitize",
        "projectName": "Tempo Async Vault",
        "teamWebsite": "https://securitize.io",
        "startDate": "2026-10-04",
        "endDate": "2026-10-05",
        "auditors": "Kage BengalCatBalu",
        "repositories": [{"sourceUrl": "https://github.com/org/repo", "commitHash": "a" * 40}],
    }
    config.update(overrides)
    return {k: v for k, v in config.items() if v is not None}


class TestParseAuditConfig:
    def test_derives_names(self, config_dir):
        config = parse_audit_config(make_config(), config_dir)
        assert config.target_repo_name == "audit-2026-10-securitize-tempo-async-vault"
        assert config.project_title == "[Audit] Securitize Tempo Async Vault (2026-10)"
        assert config.review_timeline == "Oct 4th - Oct 5th, 2026"
        assert config.auditors == ["Kage", "BengalCatBalu"]
        assert "src/Vault.sol" in config.scope_markdown

    def test_team_contained_in_project(self, config_dir):
        config = parse_audit_config(make_config(teamName="Aztec", projectName="Aztec Polynomial"), config_dir)
        assert config.target_repo_name == "audit-2026-10-aztec-polynomial"
        assert config.project_title == "[Audit] Aztec Polynomial (2026-10)"

    def test_auditors_extra_whitespace(self, config_dir):
        assert parse_audit_config(make_config(auditors="  Kage   Dacian "), config_dir).auditors == ["Kage", "Dacian"]

    def test_custom_scope_file(self, config_dir, tmp_path):
        (tmp_path / "other.md").write_text("custom scope")
        assert parse_audit_config(make_config(scopeFile="other.md"), config_dir).scope_markdown == "custom scope"

    @pytest.mark.parametrize("field", ["teamName", "projectName", "teamWebsite", "startDate", "endDate", "auditors", "repositories"])
    def test_missing_required_field(self, config_dir, field):
        config = make_config()
        del config[field]
        with pytest.raises(ValueError):
            parse_audit_config(config, config_dir)

    @pytest.mark.parametrize("field", ["targetRepoName", "projectTitle"])
    def test_legacy_fields_rejected(self, config_dir, field):
        with pytest.raises(ValueError, match="no longer supported"):
            parse_audit_config(make_config(**{field: "x"}), config_dir)

    def test_end_before_start(self, config_dir):
        with pytest.raises(ValueError, match="before"):
            parse_audit_config(make_config(startDate="2026-10-05", endDate="2026-10-04"), config_dir)

    def test_invalid_date(self, config_dir):
        with pytest.raises(ValueError, match="ISO date"):
            parse_audit_config(make_config(startDate="Oct 4th"), config_dir)

    def test_website_must_be_url(self, config_dir):
        with pytest.raises(ValueError, match="URL"):
            parse_audit_config(make_config(teamWebsite="securitize.io"), config_dir)

    def test_missing_scope_file(self, tmp_path):
        with pytest.raises(ValueError, match="Scope file"):
            parse_audit_config(make_config(), str(tmp_path))

    def test_empty_scope_file(self, tmp_path):
        (tmp_path / "scope.md").write_text("  \n")
        with pytest.raises(ValueError, match="empty"):
            parse_audit_config(make_config(), str(tmp_path))
