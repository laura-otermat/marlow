from types import SimpleNamespace

import pytest

from app.models.memory import Memory
from app.services import llm


class FakeResponses:
    def __init__(self, output_parsed):
        self.output_parsed = output_parsed
        self.call = None

    def parse(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(output_parsed=self.output_parsed)


class FakeOpenAIClient:
    def __init__(self, output_parsed):
        self.responses = FakeResponses(output_parsed)


def test_extract_memory_uses_injected_client_and_structured_output():
    memory = Memory(
        category="school",
        subject="uniforms",
        value="Children do not wear uniforms",
    )
    fake_client = FakeOpenAIClient(memory)

    result = llm.extract_memory("My kids don't wear uniforms.", openai_client=fake_client)

    assert result is memory
    assert fake_client.responses.call["model"] == "gpt-5-mini"
    assert fake_client.responses.call["text_format"] is Memory
    assert fake_client.responses.call["input"][1]["content"] == "My kids don't wear uniforms."


def test_extract_memory_rejects_missing_parsed_output():
    with pytest.raises(ValueError, match="structured memory"):
        llm.extract_memory("Hello!", openai_client=FakeOpenAIClient(None))


def test_extract_memory_propagates_provider_errors():
    class FailedResponses:
        def parse(self, **_kwargs):
            raise RuntimeError("provider failure")

    fake_client = SimpleNamespace(responses=FailedResponses())

    with pytest.raises(RuntimeError, match="provider failure"):
        llm.extract_memory("A household fact", openai_client=fake_client)


def test_extract_memory_requires_key_only_when_no_client_is_injected(monkeypatch):
    monkeypatch.setattr(llm.settings, "openai_api_key", None)

    with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
        llm.extract_memory("A household fact")

