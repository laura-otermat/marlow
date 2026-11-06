import re

from pydantic import BaseModel, Field, field_validator


class HouseholdCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    owner_email: str = Field(min_length=5, max_length=254)

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Household name cannot be blank.")
        return value

    @field_validator("owner_email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("A valid email address is required.")
        return value


class HouseholdInviteRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        value = value.strip().lower()
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
            raise ValueError("A valid email address is required.")
        return value


class HouseholdInviteResponse(BaseModel):
    email: str
    user_id: str
    household_id: str
    role: str
    invitation_sent: bool
