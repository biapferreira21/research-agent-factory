import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.retrieval.context import RetrievalConfig
from app.retrieval.evaluation import RetrievalCase
from app.retrieval.local import LocalIndex, Source
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def harness(tmp_path, case, *, limit_chars=12000, planner=offline_planner):
    (tmp_path / "notes.txt").write_text("baseline")
    index = LocalIndex(tmp_path, [Source(path="notes.txt", scope="global")])
    return BuilderHarness(root=tmp_path / "builds", event_sink=None,
                          retrieval=RetrievalConfig(index, max_context_chars=limit_chars),
                          retrieval_cases=(case,), planner=planner,
                          builder_factory=OfflineBuilder, capability_planner=offline_capability_planner,
                          test_runner=lambda _: PytestResult(0, "ok"))


def test_gate_passes_and_precedes_planning(tmp_path):
    case = RetrievalCase(name="positive", query="baseline", expected_sources=("notes.txt",))
    result = harness(tmp_path, case).build("baseline")
    assert result.status == "passed"
    directory = Path(result.telemetry_path)
    report = json.loads((directory / "retrieval_evaluation.json").read_text())
    assert report["passed_count"] == 1
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert [(event["stage"], event["status"]) for event in events[:3]] == [
        ("retrieval_evaluation", "started"), ("retrieval_evaluation", "passed"), ("retrieval", "started")]


@pytest.mark.parametrize("research", [False, True])
def test_gate_blocks_both_build_paths_before_models(tmp_path, research):
    case = RetrievalCase(name="positive", query="baseline", expected_sources=("notes.txt",))
    factory = harness(tmp_path, case, limit_chars=2,
                      planner=lambda _: pytest.fail("Planner must not run"))
    factory.question_formalizer = lambda _: pytest.fail("Formalizer must not run")
    result = factory.build_research("baseline") if research else factory.build("baseline")
    assert result.status == "blocked"
    assert result.workspace == ""
    assert result.costs.calls == 0
    directory = Path(result.telemetry_path)
    assert not (directory / "retrieval_snapshot.json").exists()
    report = json.loads((directory / "retrieval_evaluation.json").read_text())
    assert report["results"][0]["missing_sources"] == ["notes.txt"]
    events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
    assert events[1]["status"] == "blocked"


def test_unknown_source_blocks_with_saved_report(tmp_path):
    case = RetrievalCase(name="invalid", query="baseline", expected_sources=("missing.txt",))
    result = harness(tmp_path, case).build("baseline")
    assert result.status == "blocked"
    report = json.loads((Path(result.telemetry_path) / "retrieval_evaluation.json").read_text())
    assert report["status"] == "invalid_suite"


def test_gate_requires_retrieval_and_nonempty_suite():
    with pytest.raises(ValueError):
        BuilderHarness(retrieval_cases=())
    with pytest.raises(ValueError):
        BuilderHarness(retrieval_cases=(RetrievalCase(name="a", query="x", expected_sources=()),))
