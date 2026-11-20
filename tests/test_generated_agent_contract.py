from inspect import getsource

from app.builder import agent as builder_agent
from app.builder import planner as builder_planner


def test_builder_agent_uses_langchain():
    """The factory's live builder must remain backed by LangChain."""
    source = getsource(builder_agent)

    assert "langchain" in source.lower()


def test_builder_agent_uses_configured_model():
    """Model selection must flow through the factory's configured router."""
    source = getsource(builder_agent)

    assert "get_model" in source


def test_agent_spec_planner_does_not_auto_retry_invalid_structured_output(monkeypatch):
    captured = {}
    monkeypatch.setattr(builder_planner, "get_model", lambda: object())
    monkeypatch.setattr(
        builder_planner,
        "create_agent",
        lambda **kwargs: captured.update(kwargs) or object(),
    )

    builder_planner.create_planner_agent()

    assert captured["response_format"].handle_errors is False
