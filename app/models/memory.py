from datetime import datetime, timezone

from pydantic import BaseModel, Field


class Memory(BaseModel):
    category: str
    subject: str
    value: str
    confidence: float | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    household_id: str | None = None
    created_by_user_id: str | None = None
