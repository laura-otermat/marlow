from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from supabase import create_client

from app.config import settings


bearer_scheme = HTTPBearer(auto_error=False)


@dataclass
class AuthenticatedUser:
    id: str
    supabase: Any


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> AuthenticatedUser:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not settings.supabase_url or not settings.supabase_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured.",
        )

    access_token = credentials.credentials
    auth_client = create_client(settings.supabase_url, settings.supabase_key)
    try:
        response = auth_client.auth.get_user(access_token)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = getattr(response, "user", None)
    user_id = getattr(user, "id", None)
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_client = create_client(settings.supabase_url, settings.supabase_key)
    user_client.postgrest.auth(access_token)
    return AuthenticatedUser(id=str(user_id), supabase=user_client)


def require_household_membership(user: AuthenticatedUser, household_id: str) -> None:
    response = (
        user.supabase.table("household_members")
        .select("household_id")
        .eq("household_id", household_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You are not a member of this household.",
        )


def require_household_owner(user: AuthenticatedUser, household_id: str) -> None:
    response = (
        user.supabase.table("household_members")
        .select("role")
        .eq("household_id", household_id)
        .eq("user_id", user.id)
        .limit(1)
        .execute()
    )
    if not response.data or response.data[0].get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only a household owner can invite members.",
        )


def require_platform_admin(user: AuthenticatedUser) -> None:
    admin_user_id = settings.platform_admin_user_id
    if not admin_user_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Household creation is not configured.",
        )
    if user.id != admin_user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the platform administrator can create households.",
        )