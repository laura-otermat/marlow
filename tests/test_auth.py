import pytest
from types import SimpleNamespace

from fastapi.testclient import TestClient

from app import auth, routes
from app.main import app
from app.models.memory import Memory


@pytest.fixture(autouse=True)
def fake_supabase_configuration(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_url", "https://test.invalid")
    monkeypatch.setattr(auth.settings, "supabase_key", "test-anon-key")


class FakeQuery:
    def __init__(self, data):
        self.data = data
        self.filters = []

    def select(self, *_args):
        return self

    def eq(self, key, value):
        self.filters.append((key, value))
        return self

    def limit(self, *_args):
        return self

    def execute(self):
        rows = [
            row for row in self.data
            if all(row.get(key) == value for key, value in self.filters)
        ]
        return SimpleNamespace(data=rows)


class FakeSupabaseClient:
    def __init__(self, user_id, household_memberships):
        self.auth = SimpleNamespace(
            get_user=lambda _token: SimpleNamespace(
                user=SimpleNamespace(id=user_id)
            )
        )
        self.postgrest = SimpleNamespace(auth=lambda _token: None)
        self.household_memberships = household_memberships

    def table(self, table_name):
        data = self.household_memberships if table_name == "household_members" else []
        return FakeQuery(data)


def test_ask_requires_bearer_token():
    response = TestClient(app).get(
        "/ask?household_id=11111111-1111-4111-8111-111111111111"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_plan_requires_bearer_token():
    response = TestClient(app).get(
        "/plan?household_id=11111111-1111-4111-8111-111111111111"
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_deprecated_invite_owner_endpoint_is_removed():
    response = TestClient(app).post("/households/invite-owner")

    assert response.status_code == 404


def test_create_household_requires_bearer_token():
    response = TestClient(app).post(
        "/households",
        json={"name": "Alpha household", "owner_email": "alpha@example.com"},
    )

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_create_household_requires_platform_admin(monkeypatch):
    user_id = "user-not-admin"
    fake_client = FakeSupabaseClient(user_id, [])
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(auth.settings, "platform_admin_user_id", "configured-admin")

    response = TestClient(app).post(
        "/households",
        headers={"Authorization": "Bearer valid-token"},
        json={"name": "Alpha household", "owner_email": "alpha@example.com"},
    )

    assert response.status_code == 403


def test_create_household_invites_owner_for_platform_admin(monkeypatch):
    admin_id = "configured-admin"
    household_id = "22222222-2222-4222-8222-222222222222"
    fake_client = FakeSupabaseClient(admin_id, [])
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(auth.settings, "platform_admin_user_id", admin_id)
    calls = []
    monkeypatch.setattr(
        routes,
        "create_household_and_invite_owner",
        lambda **kwargs: calls.append(kwargs) or {
            "email": "alpha@example.com",
            "user_id": "invited-user",
            "household_id": household_id,
            "role": "owner",
            "invitation_sent": True,
        },
    )

    response = TestClient(app).post(
        "/households",
        headers={"Authorization": "Bearer valid-token"},
        json={"name": "  Alpha household ", "owner_email": " ALPHA@example.com "},
    )

    assert response.status_code == 201
    assert response.json() == {
        "email": "alpha@example.com",
        "user_id": "invited-user",
        "household_id": household_id,
        "role": "owner",
        "invitation_sent": True,
    }
    assert calls == [{
        "name": "Alpha household",
        "owner_email": "alpha@example.com",
        "created_by_user_id": admin_id,
    }]


def test_create_household_fails_closed_when_admin_not_configured(monkeypatch):
    user_id = "user-123"
    fake_client = FakeSupabaseClient(user_id, [])
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(auth.settings, "platform_admin_user_id", None)

    response = TestClient(app).post(
        "/households",
        headers={"Authorization": "Bearer valid-token"},
        json={"name": "Alpha household", "owner_email": "alpha@example.com"},
    )

    assert response.status_code == 503


def test_invite_member_requires_household_owner(monkeypatch):
    user_id = "member-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id,
        [{"household_id": household_id, "user_id": user_id, "role": "member"}],
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(
        routes,
        "invite_household_member",
        lambda *_args: (_ for _ in ()).throw(AssertionError("must not invite")),
    )

    response = TestClient(app).post(
        f"/households/{household_id}/invitations",
        headers={"Authorization": "Bearer valid-token"},
        json={"email": "alpha2@example.com"},
    )

    assert response.status_code == 403


def test_invite_member_allows_household_owner(monkeypatch):
    user_id = "owner-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id,
        [{"household_id": household_id, "user_id": user_id, "role": "owner"}],
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    calls = []
    monkeypatch.setattr(
        routes,
        "invite_household_member",
        lambda *args: calls.append(args) or {
            "email": "alpha2@example.com",
            "user_id": "invited-user",
            "household_id": household_id,
            "role": "member",
            "invitation_sent": True,
        },
    )

    response = TestClient(app).post(
        f"/households/{household_id}/invitations",
        headers={"Authorization": "Bearer valid-token"},
        json={"email": "ALPHA2@example.com"},
    )

    assert response.status_code == 201
    assert response.json()["role"] == "member"
    assert response.json()["invitation_sent"] is True
    assert calls == [(household_id, "alpha2@example.com")]


def test_invite_member_maps_duplicate_membership_to_conflict(monkeypatch):
    user_id = "owner-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id,
        [{"household_id": household_id, "user_id": user_id, "role": "owner"}],
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)

    def duplicate_invitation(*_args):
        from app.services.household_account import HouseholdInvitationConflict

        raise HouseholdInvitationConflict

    monkeypatch.setattr(routes, "invite_household_member", duplicate_invitation)

    response = TestClient(app).post(
        f"/households/{household_id}/invitations",
        headers={"Authorization": "Bearer valid-token"},
        json={"email": "already@example.com"},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "This user is already a member of the household."


def test_invite_member_provider_error_does_not_leak_details(monkeypatch):
    user_id = "owner-user"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id,
        [{"household_id": household_id, "user_id": user_id, "role": "owner"}],
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(
        routes,
        "invite_household_member",
        lambda *_args: (_ for _ in ()).throw(RuntimeError("private provider detail")),
    )

    response = TestClient(app).post(
        f"/households/{household_id}/invitations",
        headers={"Authorization": "Bearer valid-token"},
        json={"email": "alpha2@example.com"},
    )

    assert response.status_code == 502
    assert "private provider detail" not in response.text


def test_ask_checks_membership_and_uses_authenticated_user(monkeypatch):
    user_id = "33333333-3333-4333-8333-333333333333"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id, [{"household_id": household_id, "user_id": user_id}]
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(routes, "ask_marlow", lambda **_kwargs: "Family summary")

    response = TestClient(app).get(
        f"/ask?household_id={household_id}",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"summary": "Family summary"}


def test_plan_checks_membership_and_uses_authenticated_user(monkeypatch):
    user_id = "33333333-3333-4333-8333-333333333333"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id, [{"household_id": household_id, "user_id": user_id}]
    )
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(routes, "plan_week", lambda **_kwargs: "Three actions")

    response = TestClient(app).get(
        f"/plan?household_id={household_id}",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 200
    assert response.json() == {"plan": "Three actions"}


def test_ask_rejects_users_without_household_membership(monkeypatch):
    user_id = "33333333-3333-4333-8333-333333333333"
    fake_client = FakeSupabaseClient(user_id, [])
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)

    response = TestClient(app).get(
        "/ask?household_id=11111111-1111-4111-8111-111111111111",
        headers={"Authorization": "Bearer valid-token"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "You are not a member of this household."


def test_remember_uses_authenticated_user_as_creator(monkeypatch):
    user_id = "33333333-3333-4333-8333-333333333333"
    household_id = "11111111-1111-4111-8111-111111111111"
    fake_client = FakeSupabaseClient(
        user_id, [{"household_id": household_id, "user_id": user_id}]
    )
    saved = {}
    monkeypatch.setattr(auth, "create_client", lambda *_args: fake_client)
    monkeypatch.setattr(
        routes,
        "extract_memory",
        lambda _message: Memory(category="home", subject="fact", value="A fact"),
    )
    monkeypatch.setattr(
        routes,
        "save_memory",
        lambda memory, _client: saved.update(memory=memory),
    )

    response = TestClient(app).post(
        "/remember",
        headers={"Authorization": "Bearer valid-token"},
        json={"message": "A fact", "household_id": household_id},
    )

    assert response.status_code == 200
    assert saved["memory"].created_by_user_id == user_id