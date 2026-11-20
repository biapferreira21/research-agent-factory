import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.planning.research_validation import protocol_digest
from app.registry.mcp import MCPRegistry
from app.schemas.research import ResearchProtocol
from app.telemetry.build import active_build
from app.telemetry.costs import BudgetBlocked
from app.telemetry.schemas import BuildStage
from app.tools.filesystem import create_filesystem_tools
from app.tools.testing import PytestResult
from harness_offline_demo import offline_capability_planner
from research_demo import create_example_protocol
from research_harness_demo import (
    DEMO_QUESTION, OfflineResearchBuilder, offline_question_formalizer,
    offline_research_planner, offline_scientific_architect,
)


def harness(tmp_path, **changes):
    options = dict(
        root=tmp_path, question_formalizer=offline_question_formalizer,
        research_planner=offline_research_planner, scientific_architect=offline_scientific_architect,
        capability_planner=offline_capability_planner, builder_factory=OfflineResearchBuilder,
        mcp_registry=MCPRegistry(), event_sink=None,
    )
    options.update(changes)
    return BuilderHarness(**options)


def test_full_offline_research_build_runs_real_pytest(tmp_path):
    events = []
    result = harness(tmp_path, event_sink=events.append).build_research(DEMO_QUESTION)
    assert result.status == "passed", result.errors
    assert [event.stage for event in events if event.status == "started"] == [
        BuildStage.RESEARCH_QUESTION, BuildStage.RESEARCH_PROTOCOL, BuildStage.SCIENTIFIC_ARCHITECT,
        BuildStage.CAPABILITIES, BuildStage.PREPARING, BuildStage.GENERATING, BuildStage.GATES, BuildStage.TESTS,
    ]
    workspace = Path(result.workspace)
    protocol = ResearchProtocol.model_validate_json((workspace / "research_protocol.json").read_text(encoding="utf-8"))
    spec = json.loads((workspace / "agent_spec.json").read_text(encoding="utf-8"))
    assert spec["research_protocol_sha256"] == protocol_digest(protocol)
    assert result.costs.calls == 0
    assert active_build.get() is None


def test_supplied_question_skips_llm_formalizer(tmp_path):
    question = create_example_protocol().question
    result = harness(tmp_path, question_formalizer=lambda _: pytest.fail("Formalizer called"),
                     test_runner=lambda _: PytestResult(0, "ok")).build_research(question)
    assert result.status == "passed"
    restored = json.loads((Path(result.workspace) / "research_question.json").read_text(encoding="utf-8"))
    assert restored == question.model_dump()


def test_unanswered_question_blocks_before_protocol_planning(tmp_path):
    question = create_example_protocol().question
    question.open_questions = ["Qual é o dataset?"]
    result = harness(tmp_path, research_planner=lambda _: pytest.fail("Planner called")).build_research(question)
    assert result.status == "blocked"
    assert "dataset" in result.errors[0]
    assert result.workspace == ""
    assert (Path(result.telemetry_path) / "research_question.json").is_file()


def test_live_factory_resolves_delegated_design_questions_as_assumptions(tmp_path):
    question = create_example_protocol().question
    question.open_questions = [
        "What specific definition of task success should the evaluation use?",
        "Which concrete benchmark set should be used?",
        "What rubric or ground-truth scoring should evaluate performance?",
        "What are the exact costs associated with each tool?",
        "How should the evaluation harness track tool-call logs?",
        "Which self-improvement mechanisms should be prioritized or combined?",
        "What is the acceptable threshold for cost increase per task?",
    ]

    result = harness(tmp_path, question_formalizer=lambda _: question,
                     allow_semantic_fallbacks=True).build_research("Please propose the evaluation design")

    assert result.status == "passed", result.errors
    restored = json.loads((Path(result.workspace) / "research_question.json").read_text(encoding="utf-8"))
    assert restored["open_questions"] == []
    assert len([item for item in restored["assumptions"] if item.startswith("Factory design assumption")]) == 7


def test_live_factory_still_blocks_information_only_the_user_can_supply(tmp_path):
    question = create_example_protocol().question
    question.open_questions = ["Which private dataset can the agent access?"]

    result = harness(tmp_path, question_formalizer=lambda _: question,
                     allow_semantic_fallbacks=True).build_research("Study a private dataset")

    assert result.status == "blocked"
    assert "private dataset" in result.errors[0]


@pytest.mark.parametrize("changed", ["question", "constraints", "open_questions"])
def test_bad_protocol_never_reaches_architect(tmp_path, changed):
    def planner(question):
        protocol = offline_research_planner(question)
        if changed == "question":
            protocol.question.question = "Outra pergunta"
        elif changed == "constraints":
            protocol.question.constraints.clear()
        else:
            protocol.open_questions = ["Falta definir o orçamento experimental"]
        return protocol
    result = harness(tmp_path, research_planner=planner,
                     scientific_architect=lambda _: pytest.fail("Architect called")).build_research(DEMO_QUESTION)
    assert result.status == "blocked"
    assert (Path(result.telemetry_path) / "research_protocol.json").is_file()


def test_live_policy_replaces_semantically_invalid_protocol(tmp_path):
    def mutating_planner(question):
        protocol = offline_research_planner(question)
        protocol.question.question = "A different question"
        return protocol

    result = harness(tmp_path, research_planner=mutating_planner,
                     allow_semantic_fallbacks=True).build_research(DEMO_QUESTION)
    assert result.status == "passed", result.errors
    protocol = json.loads((Path(result.workspace) / "research_protocol.json").read_text(encoding="utf-8"))
    question = json.loads((Path(result.workspace) / "research_question.json").read_text(encoding="utf-8"))
    assert protocol["question"] == question


def test_architect_cannot_mutate_original_protocol_or_choose_its_hash(tmp_path):
    def architect(protocol):
        spec = offline_scientific_architect(protocol)
        protocol.seeds.append(99)
        spec.research_protocol_sha256 = "a" * 64
        return spec
    result = harness(tmp_path, scientific_architect=architect,
                     test_runner=lambda _: PytestResult(0, "ok")).build_research(DEMO_QUESTION)
    data = json.loads((Path(result.workspace) / "research_protocol.json").read_text(encoding="utf-8"))
    spec = json.loads((Path(result.workspace) / "agent_spec.json").read_text(encoding="utf-8"))
    assert 99 not in data["seeds"]
    assert spec["research_protocol_sha256"] != "a" * 64


def test_scientific_agent_requires_evaluations(tmp_path):
    def architect(protocol):
        spec = offline_scientific_architect(protocol)
        spec.evaluations = []
        return spec
    result = harness(tmp_path, scientific_architect=architect).build_research(DEMO_QUESTION)
    assert result.status == "blocked"


@pytest.mark.parametrize("filename", ["research_request.json", "research_question.json", "research_protocol.json"])
def test_research_files_are_read_only_to_builder_tools(tmp_path, filename):
    tools = {tool.name: tool for tool in create_filesystem_tools(tmp_path)}
    with pytest.raises(ValueError, match="read-only"):
        tools["write_file"].invoke({"path": filename, "content": "{}"})


def test_research_protocol_tampering_is_detected(tmp_path):
    class TamperingBuilder(OfflineResearchBuilder):
        def __init__(self, workspace):
            super().__init__(workspace)
            self.workspace = workspace
        def invoke(self, payload, *, config):
            super().invoke(payload, config=config)
            (self.workspace / "research_protocol.json").write_text("{}", encoding="utf-8")
    result = harness(tmp_path, builder_factory=TamperingBuilder,
                     test_runner=lambda _: pytest.fail("Tests ran after tampering")).build_research(DEMO_QUESTION)
    assert result.status == "failed"
    assert "research_protocol.json" in result.errors[0]


def test_research_stages_use_same_build_budget(tmp_path):
    def planner(question):
        active_build.get().tracker.reserve("expensive", 2)
        pytest.fail("Budget not enforced")
    result = harness(tmp_path, research_planner=planner).build_research(DEMO_QUESTION)
    assert result.status == "blocked"
    assert result.costs.budget_usd == 1
    assert active_build.get() is None


def test_malformed_structured_responses_use_validated_fallback_contracts(tmp_path):
    class ResponseValidationError(Exception):
        pass

    def malformed(*_):
        raise ResponseValidationError("provider returned malformed JSON")

    result = harness(
        tmp_path,
        question_formalizer=malformed,
        research_planner=malformed,
        scientific_architect=malformed,
        capability_planner=malformed,
    ).build_research(DEMO_QUESTION)

    assert result.status == "passed", result.errors
    workspace = Path(result.workspace)
    question = json.loads((workspace / "research_question.json").read_text(encoding="utf-8"))
    protocol = json.loads((workspace / "research_protocol.json").read_text(encoding="utf-8"))
    assert question["question"] and protocol["question"] == question
    assert protocol["seeds"] == [11, 22, 33]
    assert json.loads((workspace / "agent_spec.json").read_text())["evaluations"]


def test_invalid_generated_research_code_becomes_validated_scaffold(tmp_path):
    class InvalidBuilder:
        def __init__(self, workspace):
            self.workspace = workspace

        def invoke(self, payload, *, config):
            (self.workspace / "broken.py").write_text("def broken(:", encoding="utf-8")

    result = harness(tmp_path, builder_factory=InvalidBuilder, max_repair_attempts=1).build_research(DEMO_QUESTION)
    assert result.status == "passed", result.errors
    assert result.fallback_used is True
    assert result.repair_attempts == 1
    workspace = Path(result.workspace)
    assert (workspace / "agent.py").is_file()
    assert not (workspace / "broken.py").exists()
