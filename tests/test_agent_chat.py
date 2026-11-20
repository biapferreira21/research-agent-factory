from types import SimpleNamespace
import pytest

from app.project_runtime import run_build, agent_chat, chat
from app.projects import ProjectStore


def test_chat_uses_agent_contract_and_keeps_conversations_separate(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Methods study", "Compare two estimation methods")
    store.add_document(project["id"], "evidence.txt", b"Method A has lower error in the recorded comparison.")
    result = run_build(store, project["id"], mode="demo")
    job_id = store.start_job(project["id"], "build")
    store.update_job(job_id, "passed", result=result)

    class FakeModel:
        def invoke(self, messages):
            assert "offline_demo" in messages[0]["content"]
            assert "Compare two estimation methods" in messages[0]["content"]
            assert "APPROVED RESEARCH QUESTION" in messages[0]["content"]
            assert "APPROVED RESEARCH PROTOCOL" in messages[0]["content"]
            assert "never claim they are missing" in messages[0]["content"]
            assert "public arXiv/Crossref literature search" in messages[0]["content"]
            assert "Only the bounded, read-only factory research tools" in messages[0]["content"]
            assert any("evidence.txt" in message["content"] for message in messages)
            assert messages[-1] == {"role": "user", "content": "What did the sources say?"}
            return SimpleNamespace(content="Method A has lower error [citation].",
                                   response_metadata={"model_name": "resolved/research-model"})

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: (assert_model_options(kwargs), FakeModel())[1])

    response = agent_chat(store, project["id"], job_id, "What did the sources say?")

    assert response["agent_id"] == job_id
    assert "lower error" in response["answer"]
    assert response["sources"][0]["source"] == "evidence.txt"
    assert response["model"] == {"provider": "openrouter", "requested": "unused-offline",
                                 "resolved": "resolved/research-model"}
    assert response["context"]["research_question"] is True
    assert response["context"]["research_protocol"] is True
    assert response["context"]["source_passages"] == 1
    assert [message["role"] for message in store.agent_messages(project["id"], job_id)] == ["user", "assistant"]
    assert store.messages(project["id"]) == []


def assert_model_options(options):
    assert options["provider"] == "openrouter"
    assert options["model"] == "unused-offline"
    assert options["tool_calling"] is False
    assert options["timeout_seconds"] == 60
    return True


def test_agent_chat_can_override_the_agents_default_model(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Override study", "Estimate treatment effects")
    result = run_build(store, project["id"], mode="demo")
    job_id = store.start_job(project["id"], "build")
    store.update_job(job_id, "passed", result=result)
    selected = {}

    class FakeModel:
        def invoke(self, messages):
            return SimpleNamespace(content="A stronger-model answer.", response_metadata={})

    def fake_get_model(**kwargs):
        selected.update(kwargs)
        return FakeModel()

    import app.models
    monkeypatch.setattr(app.models, "get_model", fake_get_model)
    response = agent_chat(store, project["id"], job_id, "Explain identification",
                          model_provider="openrouter", model="strong/research-model")

    assert selected == {"tool_calling": False, "provider": "openrouter",
                        "model": "strong/research-model", "timeout_seconds": 60}
    assert response["model"]["requested"] == "strong/research-model"


def test_agent_chat_retrieves_literature_and_applies_relevant_skills(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Literature study", "How does optimizer choice affect neural network compression?")
    result = run_build(store, project["id"], mode="demo")
    job_id = store.start_job(project["id"], "build")
    store.update_job(job_id, "passed", result=result)

    import app.project_runtime as runtime
    monkeypatch.setattr(runtime, "_search_literature", lambda *args: (
        "optimizer neural network compression",
        [{"citation": "arxiv:2401.00001", "title": "Compression and Optimizers",
          "url": "https://arxiv.org/abs/2401.00001", "summary": "Evidence", "published": "2024",
          "provider": "arxiv"}],
        [],
    ))

    class FakeModel:
        def invoke(self, messages):
            assert any("Compression and Optimizers" in message["content"] for message in messages)
            assert any("dougtrajano-arxiv-search" in message["content"] for message in messages)
            return SimpleNamespace(content="Relevant evidence [arxiv:2401.00001].", response_metadata={})

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: FakeModel())
    response = agent_chat(store, project["id"], job_id,
                          "Search arXiv for relevant papers and use them as sources.")

    assert response["context"]["external_papers"] == 1
    assert response["literature"][0]["citation"] == "arxiv:2401.00001"
    assert "dougtrajano-arxiv-search" in response["effective_skills"]
    assert "factory-web/web_search" in response["tools"]


def test_failed_factory_reply_keeps_the_prompt_and_exposes_working_stage(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Connection test", "Research question")
    stages = []

    class FailingModel:
        def invoke(self, messages):
            raise ConnectionError("offline")

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: FailingModel())
    with pytest.raises(ConnectionError):
        chat(store, project["id"], "Please compare these methods", mode="live", progress=stages.append)

    assert stages == ["Searching project evidence with BM25",
                      "Preparing research context and selected skills",
                      "Waiting for the configured model to write a reply"]
    messages = store.messages(project["id"])
    assert [(message["role"], message["content"]) for message in messages] == [
        ("user", "Please compare these methods")]


def test_factory_chat_messages_linked_to_chat_job_are_visible(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Factory transcript", "Compare two research methods")
    job_id = store.start_job(project["id"], "chat")

    response = chat(store, project["id"], "Show the matching evidence",
                    mode="sources", agent_id=job_id)

    assert response["mode"] == "sources"
    messages = store.messages(project["id"])
    assert [(message["role"], message["agent_id"]) for message in messages] == [
        ("user", job_id), ("assistant", job_id)]


def test_factory_chat_replaces_provider_tool_marker_with_visible_answer(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Readable factory", "Compare two research methods")

    class LeakyModel:
        def invoke(self, messages):
            return SimpleNamespace(content="<|tool_call_start|>[retrieve_evidence()]<|tool_call_end|>",
                                   response_metadata={})

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: LeakyModel())
    response = chat(store, project["id"], "What is the research question?", mode="live")

    assert "Compare two research methods" in response["answer"]
    assert "tool_call" not in response["answer"]


def test_factory_readiness_answer_uses_python_gate_not_model_opinion(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create(
        "Ready factory",
        "Do different optimization methods affect neural network compression quality?",
    )

    class ContradictingModel:
        def invoke(self, messages):
            assert "PYTHON READINESS: READY" in messages[0]["content"]
            assert "COMPILED RESEARCH BRIEF" in messages[0]["content"]
            return SimpleNamespace(content="No, the brief is not ready.", response_metadata={})

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: ContradictingModel())
    response = chat(store, project["id"], "Is this brief ready to build?", mode="live")

    assert response["research_status"]["ready"] is True
    assert response["answer"].startswith("Yes.")
    assert "BUILD_READY" in response["answer"]


def test_agent_chat_replaces_provider_tool_marker_with_visible_answer(tmp_path, monkeypatch):
    store = ProjectStore(tmp_path)
    project = store.create("Readable agent", "Compare two research methods")
    result = run_build(store, project["id"], mode="demo")
    job_id = store.start_job(project["id"], "build")
    store.update_job(job_id, "passed", result=result)

    class LeakyModel:
        def invoke(self, messages):
            return SimpleNamespace(content="<|tool_call_start|>[retrieve_evidence()]<|tool_call_end|>",
                                   response_metadata={})

    import app.models
    monkeypatch.setattr(app.models, "get_model", lambda **kwargs: LeakyModel())
    response = agent_chat(store, project["id"], job_id, "What is the research question?")

    assert "Compare two research methods" in response["answer"]
    assert "tool_call" not in response["answer"]
