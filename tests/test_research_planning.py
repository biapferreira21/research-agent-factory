import json

import pytest

import app.planning.research_planner as planning
import app.planning.scientific_architect as architect
from app.planning.research_validation import ResearchPlanningBlocked, protocol_digest
from app.schemas.research import ResearchProtocol
from research_demo import create_example_protocol
from research_harness_demo import offline_scientific_architect


def test_formalizer_receives_original_request(monkeypatch):
    question = create_example_protocol().question
    class Fake:
        def invoke(self, payload):
            assert payload["messages"][0]["content"] == "original request"
            return {"structured_response": question}
    monkeypatch.setattr(planning, "create_question_formalizer", lambda: Fake())
    assert planning.formalize_research_question("original request") == question


def test_empty_question_does_not_construct_model(monkeypatch):
    monkeypatch.setattr(planning, "create_question_formalizer", lambda: pytest.fail("Model created"))
    with pytest.raises(ValueError):
        planning.formalize_research_question("  ")


def test_structured_research_planners_do_not_retry_invalid_responses(monkeypatch):
    captured = []
    monkeypatch.setattr(planning, "get_model", lambda: object())
    monkeypatch.setattr(
        planning,
        "create_agent",
        lambda **kwargs: captured.append(kwargs["response_format"]) or object(),
    )

    planning.create_question_formalizer()
    planning.create_research_planner()

    assert len(captured) == 2
    assert all(strategy.handle_errors is False for strategy in captured)


def test_planner_receives_complete_question(monkeypatch):
    protocol = create_example_protocol()
    class Fake:
        def invoke(self, payload):
            assert json.loads(payload["messages"][0]["content"]) == protocol.question.model_dump()
            return {"structured_response": protocol}
    monkeypatch.setattr(planning, "create_research_planner", lambda: Fake())
    assert planning.create_research_protocol(protocol.question) == protocol


def test_real_planner_wrapper_rejects_changed_question(monkeypatch):
    protocol = create_example_protocol()
    changed = protocol.model_copy(deep=True)
    changed.question.constraints.clear()
    class Fake:
        def invoke(self, payload):
            return {"structured_response": changed}
    monkeypatch.setattr(planning, "create_research_planner", lambda: Fake())
    with pytest.raises(ResearchPlanningBlocked):
        planning.create_research_protocol(protocol.question)


def test_architect_receives_whole_protocol_and_instructions(monkeypatch):
    protocol = create_example_protocol()
    expected = offline_scientific_architect(protocol)
    def fake_create(requirement):
        assert protocol.model_dump_json(indent=2) in requirement
        assert "provenance" in requirement
        assert "Do not claim" in requirement
        return expected
    monkeypatch.setattr(architect, "create_agent_spec", fake_create)
    assert architect.create_scientific_agent_spec(protocol) == expected


def test_digest_is_stable_across_json_formatting_but_changes_with_protocol():
    protocol = create_example_protocol()
    restored = ResearchProtocol.model_validate_json(protocol.model_dump_json(indent=4))
    assert protocol_digest(protocol) == protocol_digest(restored)
    restored.seeds.append(44)
    assert protocol_digest(protocol) != protocol_digest(restored)
