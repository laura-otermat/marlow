import logging
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock

from app.models.memory import Memory
from app.services.memory_repository import save_memory


def test_memory_creation():
    memory = Memory(
        category="school",
        subject="uniforms",
        value="Children do not wear uniforms",
        household_id="household-123",
        created_by_user_id="user-456",
    )

    assert memory.category == "school"
    assert memory.household_id == "household-123"
    assert memory.created_by_user_id == "user-456"
    assert memory.model_dump()["household_id"] == "household-123"


def test_memory_created_at_is_per_instance_and_utc(monkeypatch):
    call_count = 0

    class FakeDateTime:
        @staticmethod
        def now(tz):
            nonlocal call_count
            call_count += 1
            return datetime(2026, 1, 1, tzinfo=tz) + timedelta(seconds=call_count)

    monkeypatch.setattr("app.models.memory.datetime", FakeDateTime)

    first = Memory(category="home", subject="fact", value="First")
    second = Memory(category="home", subject="fact", value="Second")

    assert first.created_at == datetime(2026, 1, 1, 0, 0, 1, tzinfo=timezone.utc)
    assert second.created_at == datetime(2026, 1, 1, 0, 0, 2, tzinfo=timezone.utc)
    assert first.created_at.tzinfo is timezone.utc
    assert second.created_at.tzinfo is timezone.utc


def test_save_memory_does_not_log_memory_or_provider_response(caplog, capsys):
    memory_secret = "private-household-memory-marker"
    response_secret = "private-provider-response-marker"
    memory = Memory(
        category="personal",
        subject="account detail",
        value=memory_secret,
        household_id="household-123",
        created_by_user_id="user-456",
    )

    class SensitiveResponse:
        def __repr__(self):
            return response_secret

    response = SensitiveResponse()
    supabase_client = Mock()
    supabase_client.table.return_value.insert.return_value.execute.return_value = response

    with caplog.at_level(logging.DEBUG):
        result = save_memory(memory, supabase_client)

    captured = capsys.readouterr()
    assert result is response
    assert memory_secret not in captured.out + captured.err + caplog.text
    assert response_secret not in captured.out + captured.err + caplog.text
    
