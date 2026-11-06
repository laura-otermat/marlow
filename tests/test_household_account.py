from types import SimpleNamespace

import pytest

from app.services import household_account


class FakeQuery:
    def __init__(self, table_name, household_id, inserts, rows=None):
        self.table_name = table_name
        self.household_id = household_id
        self.inserts = inserts
        self.payload = None
        self.rows = rows or []

    def insert(self, payload):
        self.payload = payload
        self.inserts.append((self.table_name, payload))
        return self

    def select(self, *_args):
        return self

    def eq(self, *_args):
        return self

    def limit(self, *_args):
        return self

    def delete(self):
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        rows = (
            [{"id": self.household_id}]
            if self.table_name == "households"
            else self.rows
        )
        return SimpleNamespace(data=rows)


class FakeAdmin:
    def __init__(self, user_id, invited, users=None):
        self.user_id = user_id
        self.invited = invited
        self.users = users or []

    def list_users(self, *, page, per_page):
        assert page == 1
        assert per_page == 1000
        return self.users

    def invite_user_by_email(self, email):
        self.invited.append(email)
        return SimpleNamespace(user=SimpleNamespace(id=self.user_id))


def make_fake_client(
    user_id, household_id, invited, inserts, users=None, membership_rows=None
):
    return SimpleNamespace(
        auth=SimpleNamespace(admin=FakeAdmin(user_id, invited, users)),
        table=lambda table_name: FakeQuery(
            table_name,
            household_id,
            inserts,
            rows=membership_rows if table_name == "household_members" else None,
        ),
    )


def test_create_household_invites_owner_and_persists_owner_membership(monkeypatch):
    user_id = "invitee-user"
    household_id = "22222222-2222-4222-8222-222222222222"
    invited = []
    inserts = []
    client = make_fake_client(user_id, household_id, invited, inserts)
    monkeypatch.setattr(household_account, "_admin_client", lambda: client)

    result = household_account.create_household_and_invite_owner(
        "Alpha household", "alpha@example.com", "platform-admin"
    )

    assert result == {
        "email": "alpha@example.com",
        "user_id": user_id,
        "household_id": household_id,
        "role": "owner",
        "invitation_sent": True,
    }
    assert invited == ["alpha@example.com"]
    assert inserts == [
        (
            "households",
            {"name": "Alpha household", "created_by_user_id": "platform-admin"},
        ),
        (
            "household_members",
            {"household_id": household_id, "user_id": user_id, "role": "owner"},
        ),
    ]


def test_invite_household_member_persists_member_role(monkeypatch):
    user_id = "invitee-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    invited = []
    inserts = []
    client = make_fake_client(user_id, household_id, invited, inserts)
    monkeypatch.setattr(household_account, "_admin_client", lambda: client)

    result = household_account.invite_household_member(household_id, "member@example.com")

    assert result["role"] == "member"
    assert result["invitation_sent"] is True
    assert invited == ["member@example.com"]
    assert inserts == [
        (
            "household_members",
            {"household_id": household_id, "user_id": user_id, "role": "member"},
        )
    ]


def test_existing_auth_user_is_added_without_sending_duplicate_invite(monkeypatch):
    user_id = "existing-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    invited = []
    inserts = []
    existing_user = SimpleNamespace(id=user_id, email="member@example.com")
    client = make_fake_client(
        user_id, household_id, invited, inserts, users=[existing_user]
    )
    monkeypatch.setattr(household_account, "_admin_client", lambda: client)

    result = household_account.invite_household_member(household_id, "member@example.com")

    assert result["user_id"] == user_id
    assert result["invitation_sent"] is False
    assert invited == []
    assert inserts == [
        (
            "household_members",
            {"household_id": household_id, "user_id": user_id, "role": "member"},
        )
    ]


def test_inviting_existing_member_returns_conflict(monkeypatch):
    user_id = "existing-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    invited = []
    inserts = []
    existing_user = SimpleNamespace(id=user_id, email="member@example.com")
    client = make_fake_client(
        user_id,
        household_id,
        invited,
        inserts,
        users=[existing_user],
        membership_rows=[{"user_id": user_id}],
    )
    monkeypatch.setattr(household_account, "_admin_client", lambda: client)

    with pytest.raises(household_account.HouseholdInvitationConflict):
        household_account.invite_household_member(household_id, "member@example.com")

    assert invited == []
    assert inserts == []


def test_admin_client_requires_service_role_key(monkeypatch):
    monkeypatch.setattr(household_account.settings, "supabase_service_role_key", None)

    with pytest.raises(RuntimeError, match="not configured"):
        household_account._admin_client()
