from pathlib import Path


def test_generated_agent_uses_langchain():
    agent_file = Path(
        "generated_agents/hello_agent/agent.py"
    )

    content = agent_file.read_text(
        encoding="utf-8"
    )

    assert "langchain" in content.lower()


def test_generated_agent_uses_configured_model():
    agent_file = Path(
        "generated_agents/hello_agent/agent.py"
    )

    content = agent_file.read_text(
        encoding="utf-8"
    )

    assert (
        "get_model" in content
        or "ChatOpenAI" in content
    )

    