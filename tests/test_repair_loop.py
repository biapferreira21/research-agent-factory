from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def factory(tmp_path, runner, builder=OfflineBuilder, attempts=2):
    return BuilderHarness(root=tmp_path, planner=offline_planner, builder_factory=builder,
                          capability_planner=offline_capability_planner, test_runner=runner,
                          event_sink=None, max_repair_attempts=attempts)


def test_failed_test_repaired_then_revalidated(tmp_path):
    results = iter([PytestResult(1, "assertion failed"), PytestResult(0, "ok")])
    calls = []
    class Builder(OfflineBuilder):
        def invoke(self, payload, *, config):
            calls.append(payload)
            super().invoke(payload, config=config)
    result = factory(tmp_path, lambda _: next(results), Builder).build("demo")
    assert result.status == "passed"
    assert result.repair_attempts == 1
    assert len(calls) == 2
    assert "assertion failed" in calls[1]["messages"][-1]["content"]
    assert (Path(result.telemetry_path) / "validation_0.json").exists()


def test_persistent_failure_stops_at_limit(tmp_path):
    result = factory(tmp_path, lambda _: PytestResult(1, "bad")).build("demo")
    assert result.status == "failed"
    assert result.repair_attempts == 2
    assert len(list(Path(result.telemetry_path).glob("validation_*.json"))) == 3


@pytest.mark.parametrize("outcome", [PytestResult(None, "timeout", True), PytestResult(3, "internal"),
                                    PytestResult(2, "interrupted"), PytestResult(4, "usage")])
def test_infrastructure_failure_does_not_retry(tmp_path, outcome):
    result = factory(tmp_path, lambda _: outcome).build("demo")
    assert result.status == "failed"
    assert result.repair_attempts == 0


def test_contract_tampering_never_repaired(tmp_path):
    def runner(workspace):
        (workspace / "agent_spec.json").write_text("{}")
        return PytestResult(1, "bad")
    result = factory(tmp_path, runner).build("demo")
    assert result.status == "failed"
    assert result.repair_attempts == 0


def test_repair_limit_validation():
    for value in (-1, 6, True, 1.5):
        with pytest.raises(ValueError):
            BuilderHarness(max_repair_attempts=value)
