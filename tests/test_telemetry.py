import json
from decimal import Decimal

import pytest

from app.builder.harness import BuilderHarness
from app.telemetry.build import active_build
from app.telemetry.costs import BudgetBlocked
from app.telemetry.schemas import BuildStage
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def read_events(directory):
    return [json.loads(line) for line in (directory / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_successful_build_has_ordered_events_and_separate_logs(tmp_path):
    seen = []
    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
        test_runner=lambda _: PytestResult(0, "ok"), event_sink=seen.append,
    ).build("demo")
    assert result.status == "passed"
    assert [(event.stage, event.status) for event in seen] == [
        (stage, status) for stage in [BuildStage.PLANNING, BuildStage.CAPABILITIES, BuildStage.PREPARING,
                                     BuildStage.GENERATING, BuildStage.GATES, BuildStage.TESTS]
        for status in ["started", "passed"]
    ] + [(BuildStage.FINISHED, "passed")]
    assert result.costs.calls == 0
    assert result.costs.budget_usd == Decimal("1.00")
    assert result.costs.unknown_calls == 0
    assert result.telemetry_path != result.workspace
    assert active_build.get() is None


def test_provider_exception_is_logged_without_secret_or_prompt(tmp_path):
    def failing_planner(_):
        raise RuntimeError("SECRET_PROVIDER_ERROR")

    with pytest.raises(RuntimeError):
        BuilderHarness(capability_planner=offline_capability_planner, root=tmp_path, planner=failing_planner, event_sink=None).build("SECRET_PROMPT")
    directory = next((tmp_path / ".factory_runs").iterdir())
    events = read_events(directory)
    assert events[-2]["stage"] == "planning"
    assert events[-2]["error_type"] == "RuntimeError"
    assert events[-1]["status"] == "failed"
    assert "SECRET" not in (directory / "events.jsonl").read_text()
    assert (directory / "cost_summary.json").is_file()
    assert active_build.get() is None


def test_budget_block_returns_result_and_logs(tmp_path):
    def planner(_):
        active_build.get().tracker.reserve("call", Decimal("2"))
        pytest.fail("Call should have been blocked")

    result = BuilderHarness(capability_planner=offline_capability_planner, root=tmp_path, planner=planner, event_sink=None).build("demo")
    assert result.status == "blocked"
    assert result.workspace == ""
    assert result.costs.calls == 0


def test_test_failure_is_not_logged_as_passed(tmp_path):
    seen = []
    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
        test_runner=lambda _: PytestResult(1, "failed"), event_sink=seen.append,
    ).build("demo")
    assert result.status == "failed"
    assert seen[-2].stage == BuildStage.TESTS
    assert seen[-2].status == "failed"


def test_reusing_harness_starts_new_accounting(tmp_path):
    harness = BuilderHarness(capability_planner=offline_capability_planner, root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
                             test_runner=lambda _: PytestResult(0, "ok"), event_sink=None)
    first = harness.build("one")
    second = harness.build("two")
    assert first.telemetry_path != second.telemetry_path
    assert second.costs.remaining_usd == Decimal("1")
