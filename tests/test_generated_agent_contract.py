from inspect import getsource

from app.builder import agent as builder_agent


def test_builder_agent_uses_langchain():
    """The factory's live builder must remain backed by LangChain."""
    source = getsource(builder_agent)

    assert "langchain" in source.lower()


def test_builder_agent_uses_configured_model():
    """Model selection must flow through the factory's configured router."""
    source = getsource(builder_agent)

    assert "get_model" in source
