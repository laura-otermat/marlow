from typing import Any

from supabase import create_client

from app.config import settings


class HouseholdServiceNotConfigured(RuntimeError):
    pass


class HouseholdInvitationConflict(Exception):
    pass


def _admin_client() -> Any:
    service_role_key: Any = settings.supabase_service_role_key
    if not settings.supabase_url or not service_role_key:
        raise HouseholdServiceNotConfigured("Household invitations are not configured.")
    return create_client(settings.supabase_url, service_role_key)


def _find_auth_user(admin_client: Any, email: str) -> Any | None:
    page = 1
    per_page = 1000
    while True:
        result = admin_client.auth.admin.list_users(page=page, per_page=per_page)
        users = getattr(result, "users", result)
        users = users or []
        for user in users:
            if (getattr(user, "email", None) or "").lower() == email.lower():
                return user
        if len(users) < per_page:
            return None
        page += 1


def _get_or_invite_user(admin_client: Any, email: str) -> tuple[str, bool]:
    existing_user = _find_auth_user(admin_client, email)
    if existing_user is not None:
        user_id = getattr(existing_user, "id", None)
        if user_id is None:
            raise RuntimeError("Supabase returned an invalid existing user.")
        return str(user_id), False

    response = admin_client.auth.admin.invite_user_by_email(email)
    user = getattr(response, "user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        raise RuntimeError("Supabase did not return an invited user.")
    return str(user_id), True


def _response_row(response: Any) -> dict[str, Any]:
    rows = getattr(response, "data", None) or []
    if not rows or not isinstance(rows[0], dict):
        raise RuntimeError("Supabase did not return the created household.")
    return rows[0]


def create_household_and_invite_owner(
    name: str, owner_email: str, created_by_user_id: str
) -> dict[str, Any]:
    """Create a household and invite its initial owner using server credentials."""
    admin_client = _admin_client()
    household = _response_row(
        admin_client.table("households")
        .insert({"name": name, "created_by_user_id": created_by_user_id})
        .select("id")
        .execute()
    )
    household_id = str(household["id"])

    try:
        owner_user_id, invitation_sent = _get_or_invite_user(admin_client, owner_email)
        admin_client.table("household_members").insert(
            {
                "household_id": household_id,
                "user_id": owner_user_id,
                "role": "owner",
            }
        ).execute()
    except Exception:
        # Best-effort cleanup avoids leaving an empty household if membership
        # provisioning fails. The Supabase Auth invite itself cannot be rolled
        # back as part of the database operation.
        try:
            admin_client.table("households").delete().eq("id", household_id).execute()
        except Exception:
            pass
        raise

    return {
        "email": owner_email,
        "user_id": owner_user_id,
        "household_id": household_id,
        "role": "owner",
        "invitation_sent": invitation_sent,
    }


def invite_household_member(household_id: str, email: str) -> dict[str, Any]:
    """Invite a user as a member of an existing household."""
    admin_client = _admin_client()
    existing_user = _find_auth_user(admin_client, email)
    if existing_user is not None:
        user_id = str(existing_user.id)
        existing_membership = (
            admin_client.table("household_members")
            .select("user_id")
            .eq("household_id", household_id)
            .eq("user_id", user_id)
            .limit(1)
            .execute()
        )
        if getattr(existing_membership, "data", None):
            raise HouseholdInvitationConflict("User is already a household member.")
        invitation_sent = False
    else:
        user_id, invitation_sent = _get_or_invite_user(admin_client, email)

    admin_client.table("household_members").insert(
        {"household_id": household_id, "user_id": user_id, "role": "member"}
    ).execute()
    return {
        "email": email,
        "user_id": user_id,
        "household_id": household_id,
        "role": "member",
        "invitation_sent": invitation_sent,
    }
