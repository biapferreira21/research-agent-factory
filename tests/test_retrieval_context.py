import json
from decimal import Decimal

import pytest

from app.builder.harness import BuilderHarness
from app.retrieval.context import RetrievalConfig, evidence_messages
from app.retrieval.local import LocalIndex, Source
from app.telemetry.build import BuildTelemetry
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def config(tmp_path, **kwargs):
    (tmp_path / "note.txt").write_text("baseline: referência local", encoding="utf-8")
    return RetrievalConfig(LocalIndex(tmp_path, [Source(path="note.txt", scope="global")]), **kwargs)


def test_context_limit_covers_serialized_metadata(tmp_path):
    snapshot = config(tmp_path, max_context_chars=2).snapshot("baseline")
    assert snapshot["context"] == "[]"
    assert snapshot["skipped_for_size"] == 1
    assert snapshot["hits"] == []


def test_harness_persists_before_planning_and_resets_context(tmp_path):
    retrieval = config(tmp_path)
    seen = []
    def planner(requirement):
        messages = evidence_messages()
        assert messages[0]["role"] == "system"
        assert "never instructions" in messages[0]["content"]
        seen.append(messages[1]["content"])
        return offline_planner(requirement)
    result = BuilderHarness(root=tmp_path / "builds", retrieval=retrieval, planner=planner,
                            builder_factory=OfflineBuilder, capability_planner=offline_capability_planner,
                            test_runner=lambda _: PytestResult(0, "ok"), event_sink=None).build("baseline")
    assert result.status == "passed"
    from pathlib import Path
    snapshot = json.loads((Path(result.telemetry_path) / "retrieval_snapshot.json").read_text(encoding="utf-8"))
    assert snapshot["context"] in seen[0]
    assert snapshot["hits"][0]["evidence"]["text"] == "baseline: referência local"
    assert not (Path(result.workspace) / "retrieval_snapshot.json").exists()
    assert evidence_messages() == []
    assert result.costs.calls == 0


def test_no_results_do_not_add_messages(tmp_path):
    telemetry = BuildTelemetry("test", tmp_path / "run", Decimal(1), sink=None)
    telemetry.retrieval_context = config(tmp_path).snapshot("absent")["context"]
    with telemetry.activate():
        assert evidence_messages() == []


def test_research_wrapper_receives_evidence_and_unchanged_question(tmp_path, monkeypatch):
    import app.planning.research_planner as planner
    from research_demo import create_example_protocol
    protocol = create_example_protocol()
    class Fake:
        def invoke(self, payload):
            messages = payload["messages"]
            assert "baseline" in messages[1]["content"]
            assert json.loads(messages[-1]["content"]) == protocol.question.model_dump()
            return {"structured_response": protocol}
    monkeypatch.setattr(planner, "create_research_planner", lambda: Fake())
    telemetry = BuildTelemetry("test", tmp_path / "run", Decimal(1), sink=None)
    telemetry.retrieval_context = config(tmp_path).snapshot("baseline")["context"]
    with telemetry.activate():
        assert planner.create_research_protocol(protocol.question) == protocol


def test_failure_keeps_snapshot_and_restores_context(tmp_path):
    def failing(_):
        assert evidence_messages()
        raise RuntimeError("planner failure")
    with pytest.raises(RuntimeError):
        BuilderHarness(root=tmp_path / "builds", retrieval=config(tmp_path),
                       planner=failing, event_sink=None).build("baseline")
    assert len(list((tmp_path / "builds").glob(".factory_runs/*/retrieval_snapshot.json"))) == 1
    assert evidence_messages() == []
