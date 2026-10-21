from __future__ import annotations

import pytest

from audit_repo_cloner.auditors import get_review_methods, grant_repo_access, resolve_github_handles, validate_auditors

MAPPING = {
    "Dacian": {"link": "https://x.com/DevDacian", "github": "devdacian"},
    "Kage": {"link": "https://x.com/0kage_eth", "github": "kage-gh"},
    "Eagle": {"link": "https://x.com/eagle", "github": "eagle-gh"},
    "NoHandle": {"link": "https://x.com/nohandle", "github": ""},
    "Alexzoid": {"link": "https://x.com/alexzoid", "suffix": "Formal Verification", "github": "alexzoid-gh"},
    "0x539": {"link": "https://x.com/1337web3", "github": "0x539-gh"},
    "PeterSR": {"link": "https://x.com/PeterSRWeb3", "github": "petersr-gh"},
    "ChainDefenders": {"link": "https://x.com/DefendersAudits", "members": ["0x539", "PeterSR"]},
    "FVTeam": {"link": "https://x.com/fvteam", "members": ["Alexzoid"]},
    "BrokenTeam": {"link": "https://x.com/broken", "members": ["Ghost"]},
}


class TestValidateAuditors:
    def test_known_auditors(self):
        validate_auditors(["Dacian", "ChainDefenders"], MAPPING)

    def test_unknown_auditor(self):
        with pytest.raises(ValueError, match="Nobody"):
            validate_auditors(["Dacian", "Nobody"], MAPPING)

    def test_names_are_case_sensitive(self):
        with pytest.raises(ValueError, match="dacian"):
            validate_auditors(["dacian"], MAPPING)

    def test_unknown_team_member(self):
        with pytest.raises(ValueError, match="Ghost"):
            validate_auditors(["BrokenTeam"], MAPPING)


class TestResolveGithubHandles:
    def test_individuals(self):
        assert resolve_github_handles(["Dacian", "Kage"], MAPPING) == ["devdacian", "kage-gh"]

    def test_team_expanded_to_members(self):
        assert resolve_github_handles(["ChainDefenders"], MAPPING) == ["0x539-gh", "petersr-gh"]

    def test_duplicates_removed(self):
        assert resolve_github_handles(["ChainDefenders", "PeterSR"], MAPPING) == ["0x539-gh", "petersr-gh"]

    def test_missing_handle(self):
        with pytest.raises(ValueError, match="NoHandle"):
            resolve_github_handles(["Dacian", "NoHandle"], MAPPING)


class TestGetReviewMethods:
    def test_manual_only(self):
        assert get_review_methods(["Dacian", "ChainDefenders"], MAPPING) == "Manual Review"

    def test_formal_verification_auditor(self):
        assert get_review_methods(["Dacian", "Alexzoid"], MAPPING) == "Manual Review, Formal Verification"

    def test_formal_verification_team_member(self):
        assert get_review_methods(["FVTeam"], MAPPING) == "Manual Review, Formal Verification"


# --- grant_repo_access ---


class FakeUser:
    def __init__(self, login):
        self.login = login


class FakeTeam:
    def __init__(self, members):
        self.members = members
        self.repo_permissions = {}

    def update_team_repository(self, repo, permission):
        self.repo_permissions[repo.name] = permission
        return True

    def get_members(self):
        return [FakeUser(m) for m in self.members]


class FakeOrg:
    def __init__(self, team):
        self.team = team

    def get_team_by_slug(self, slug):
        assert slug == "auditors"
        return self.team


class FakeGithub:
    def __init__(self, team):
        self.org = FakeOrg(team)

    def get_organization(self, organization):
        return self.org


class FakeRepo:
    name = "audit-2026-10-test"

    def __init__(self):
        self.invited = {}

    def add_to_collaborators(self, handle, permission=None):
        self.invited[handle] = permission


class TestGrantRepoAccess:
    def test_team_gets_admin_and_only_external_auditors_invited(self):
        team = FakeTeam(["DevDacian", "kage-gh"])
        repo = FakeRepo()
        grant_repo_access(FakeGithub(team), "Cyfrin", repo, ["devdacian", "kage-gh", "eagle-gh"])
        assert team.repo_permissions == {repo.name: "admin"}
        assert repo.invited == {"eagle-gh": "push"}

    def test_no_auditors_to_invite(self):
        team = FakeTeam([])
        repo = FakeRepo()
        grant_repo_access(FakeGithub(team), "Cyfrin", repo, [])
        assert team.repo_permissions == {repo.name: "admin"}
        assert repo.invited == {}
