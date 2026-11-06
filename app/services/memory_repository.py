from datetime import datetime
from typing import Any

from pydantic import BaseModel


def _to_json_serializable(obj: Any) -> Any:
    if isinstance(obj, BaseModel):
        return _to_json_serializable(obj.model_dump(mode="json"))
    if isinstance(obj, dict):
        return {k: _to_json_serializable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_json_serializable(v) for v in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj


def _require_household_metadata(memory: Any) -> dict[str, Any]:
    payload = _to_json_serializable(memory)
    household_id = payload.get("household_id") if isinstance(payload, dict) else None
    created_by_user_id = payload.get("created_by_user_id") if isinstance(payload, dict) else None

    if household_id is None or created_by_user_id is None:
        raise ValueError("Memory must include both household_id and created_by_user_id.")

    return payload


def save_memory(memory: Any, supabase_client: Any):
    """Save a Memory (pydantic model or dict) to Supabase.

    Converts pydantic models and datetimes to JSON-serializable types before
    sending to the client.
    """
    payload = _require_household_metadata(memory)

    response = (
        supabase_client
        .table("memories")
        .insert(payload)
        .execute()
    )

    return response


def get_memories(household_id: str, supabase_client: Any):
    query = supabase_client.table("memories").select("*").eq("household_id", household_id)

    response = query.execute()
    return response.data

