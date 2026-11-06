from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from app.auth import (
    AuthenticatedUser,
    get_current_user,
    require_household_membership,
    require_household_owner,
    require_platform_admin,
)
from app.models.household import (
    HouseholdCreateRequest,
    HouseholdInviteRequest,
    HouseholdInviteResponse,
)
from app.models.request import RememberRequest
from app.services.agent import ask_marlow, plan_week
from app.services.household_account import (
    HouseholdInvitationConflict,
    HouseholdServiceNotConfigured,
    create_household_and_invite_owner,
    invite_household_member,
)
from app.services.llm import extract_memory
from app.services.memory_repository import save_memory

router = APIRouter()


@router.post(
    "/households",
    response_model=HouseholdInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_household(
    request: HouseholdCreateRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    require_platform_admin(user)
    try:
        invitation = create_household_and_invite_owner(
            name=request.name,
            owner_email=request.owner_email,
            created_by_user_id=user.id,
        )
    except HouseholdServiceNotConfigured as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Household creation or invitation is not configured.",
        ) from None
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase could not create the household invitation.",
        ) from None
    return HouseholdInviteResponse(**invitation)


@router.post(
    "/households/{household_id}/invitations",
    response_model=HouseholdInviteResponse,
    status_code=status.HTTP_201_CREATED,
)
def invite_member(
    household_id: UUID,
    request: HouseholdInviteRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    household_id = str(household_id)
    require_household_owner(user, household_id)
    try:
        invitation = invite_household_member(household_id, request.email)
    except HouseholdServiceNotConfigured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Household invitation is not configured.",
        ) from None
    except HouseholdInvitationConflict:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This user is already a member of the household.",
        ) from None
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Supabase could not create the household invitation.",
        ) from None
    return HouseholdInviteResponse(**invitation)


@router.post("/remember")
def remember(
    request: RememberRequest,
    user: AuthenticatedUser = Depends(get_current_user),
):
    require_household_membership(user, request.household_id)
    memory = extract_memory(request.message)
    memory.household_id = request.household_id
    memory.created_by_user_id = user.id

    save_memory(memory, user.supabase)
    return memory.model_dump(mode="json")


@router.get("/ask")
def ask(
    household_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    require_household_membership(user, household_id)
    return {
        "summary": ask_marlow(household_id=household_id, supabase_client=user.supabase)
    }


@router.get("/plan")
def plan(
    household_id: str,
    user: AuthenticatedUser = Depends(get_current_user),
):
    require_household_membership(user, household_id)
    return {
        "plan": plan_week(household_id=household_id, supabase_client=user.supabase)
    }

