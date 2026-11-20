from decimal import Decimal
from uuid import uuid4

import pytest

from app.telemetry.build import BuildTelemetry
from app.telemetry.report import build_report
from app.telemetry.schemas import BuildStage


def setup(tmp_path):
    identifier = str(uuid4())
    telemetry = BuildTelemetry(identifier, tmp_path / ".factory_runs" / identifier, Decimal(1), sink=None)
    return identifier, telemetry


def test_completed_build_and_repairs(tmp_path):
    identifier, telemetry = setup(tmp_path)
    with telemetry.stage(BuildStage.REPAIRING):
        pass
    telemetry.finish("passed")
    report = build_report(tmp_path, identifier)
    assert report["status"] == "passed"
    assert report["repair_attempts_started"] == 1
    assert report["costs_at_last_event"]["calls"] == 0


def test_interrupted_build_is_not_passed(tmp_path):
    identifier, telemetry = setup(tmp_path)
    telemetry.emit(BuildStage.GENERATING, "started")
    assert build_report(tmp_path, identifier)["status"] == "incomplete"


def test_corrupt_trailing_line_marks_logs_unreliable(tmp_path):
    identifier, telemetry = setup(tmp_path)
    telemetry.finish("passed")
    with (telemetry.directory / "events.jsonl").open("a") as handle:
        handle.write('{"truncated":')
    report = build_report(tmp_path, identifier)
    assert report["status"] == "unreliable_logs"
    assert report["issues"]


def test_unknown_or_escaping_id_rejected(tmp_path):
    with pytest.raises(ValueError):
        build_report(tmp_path, "../elsewhere")
    with pytest.raises(FileNotFoundError):
        build_report(tmp_path, str(uuid4()))


def test_only_verified_linked_evaluations_are_listed(tmp_path):
    from uuid import UUID
    from app.planning.result_store import save_evaluation
    from research_demo import create_example_protocol
    from results_demo import create_synthetic_results
    identifier, telemetry = setup(tmp_path)
    telemetry.finish("passed")
    protocol = create_example_protocol()
    results = create_synthetic_results(protocol).model_copy(update={"source_build_id": UUID(identifier)})
    archive = save_evaluation(tmp_path / ".research_evaluations", protocol, results)
    report = build_report(tmp_path, identifier)
    assert len(report["research_evaluations"]) == 1
    assert report["research_evaluations"][0]["origin"] == "synthetic"
    (archive / "evaluation.json").write_text("{}")
    report = build_report(tmp_path, identifier)
    assert report["research_evaluations"] == []
    assert report["issues"]
