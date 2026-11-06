from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from app.services import agent


class FakeResponses:
    def __init__(self):
        self.call = None

    def create(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(output_text="Nothing urgent.")


def test_plan_week_includes_explicit_utc_date_and_monday_sunday_range(monkeypatch):
    monkeypatch.setattr(agent, "get_memories", lambda *_args: [])
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)

    result = agent.plan_week(
        "household-id",
        object(),
        openai_client=client,
        current_time=datetime(2026, 11, 5, 23, 30, tzinfo=timezone.utc),
    )

    assert result == "Nothing urgent."
    prompt = responses.call["input"]
    assert "Current date (UTC): 2026-11-05." in prompt
    assert (
        "Current planning week (Monday through Sunday, UTC): "
        "2026-11-02 through 2026-11-08."
    ) in prompt


def test_plan_week_converts_clock_to_utc_before_finding_week(monkeypatch):
    monkeypatch.setattr(agent, "get_memories", lambda *_args: [])
    responses = FakeResponses()
    client = SimpleNamespace(responses=responses)

    agent.plan_week(
        "household-id",
        object(),
        openai_client=client,
        current_time=datetime.fromisoformat("2026-11-02T00:30:00+02:00"),
    )

    prompt = responses.call["input"]
    assert "Current date (UTC): 2026-11-01." in prompt
    assert (
        "Current planning week (Monday through Sunday, UTC): "
        "2026-10-26 through 2026-11-01."
    ) in prompt


def test_plan_week_rejects_naive_clock(monkeypatch):
    monkeypatch.setattr(agent, "get_memories", lambda *_args: [])

    with pytest.raises(ValueError, match="timezone-aware"):
        agent.plan_week(
            "household-id",
            object(),
            openai_client=SimpleNamespace(responses=FakeResponses()),
            current_time=datetime(2026, 11, 5),
        )
