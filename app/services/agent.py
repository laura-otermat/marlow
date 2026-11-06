from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.memory_repository import get_memories
from app.services.llm import create_openai_client


def ask_marlow(
    household_id: str, supabase_client, *, openai_client: Any | None = None
):
    memories = get_memories(household_id, supabase_client)
    if openai_client is None:
        openai_client = create_openai_client()

    response = openai_client.responses.create(
        model="gpt-5-mini",
        input=f"""
You are Marlow, a household assistant.

Rules:
- Give a concise, useful summary of the household's saved memories.
- Group related details where helpful.
- Do not invent details or add advice that is not supported by the memories.
- If there are no saved memories, say so plainly.

Household memories:
{memories}
"""
    )

    return response.output_text


def plan_week(
    household_id: str,
    supabase_client,
    *,
    openai_client: Any | None = None,
    current_time: datetime | None = None,
):
    memories = get_memories(household_id, supabase_client)
    if openai_client is None:
        openai_client = create_openai_client()

    current_time = current_time or datetime.now(timezone.utc)
    if current_time.tzinfo is None or current_time.utcoffset() is None:
        raise ValueError("current_time must be timezone-aware.")
    current_date = current_time.astimezone(timezone.utc).date()
    week_start = current_date - timedelta(days=current_date.weekday())
    week_end = week_start + timedelta(days=6)

    response = openai_client.responses.create(
        model="gpt-5-mini",
        input=f"""
You are Marlow, a household assistant.
Your job is to reduce the user's mental load. Choose 3 action items the user should take this week
to prepare for upcoming events.

Rules:
- Be concise.
- Prioritize actions over explanations.
- Only mention things that require attention.
- Do not summarize all memories.
- If nothing requires attention, say "Nothing urgent."
- Prefer a short checklist.
- Use UTC as the household planning timezone.
- Current date (UTC): {current_date.isoformat()}.
- Current planning week (Monday through Sunday, UTC): {week_start.isoformat()} through {week_end.isoformat()}.
- Judge event urgency relative to this explicit date and week range.

Household memories:
{memories}
"""
    )

    return response.output_text


