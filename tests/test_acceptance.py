import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def factory(tmp_path, validator, builder=OfflineBuilder, attempts=0):
    return BuilderHarness(root=tmp_path, planner=offline_planner, builder_factory=builder,
                          capability_planner=offline_capability_planner,
                          test_runner=lambda _: PytestResult(0, "generated tests passed"),
                          acceptance_validator=validator, max_repair_attempts=attempts, event_sink=None)


def test_generated_tests_passing_does_not_override_acceptance(tmp_path):
    result = factory(tmp_path, lambda _: ["Required behavior missing"]).build("demo")
    assert result.status == "failed"
    assert result.errors == ["Required behavior missing"]
    report = json.loads((Path(result.telemetry_path) / "acceptance.jsonl").read_text())
    assert report["passed"] is False


def test_external_validator_rechecks_after_repair(tmp_path):
    class Builder(OfflineBuilder):
        def __init__(self, workspace):
            super().__init__(workspace)
            self.workspace = workspace
        def invoke(self, payload, *, config):
            super().invoke(payload, config=config)
            if len(payload["messages"]) > 1:
                (self.workspace / "README.md").write_text("Usage: greet(name)")
    def acceptance(workspace):
        return [] if (workspace / "README.md").is_file() else ["README.md is required"]
    result = factory(tmp_path, acceptance, Builder, attempts=1).build("demo")
    assert result.status == "passed"
    assert result.repair_attempts == 1
    records = [json.loads(line) for line in (Path(result.telemetry_path) / "acceptance.jsonl").read_text().splitlines()]
    assert [record["passed"] for record in records] == [False, True]


@pytest.mark.parametrize("invalid", [None, True, "ok", [""], [1]])
def test_invalid_validator_output_cannot_pass(tmp_path, invalid):
    with pytest.raises(TypeError):
        factory(tmp_path, lambda _: invalid, attempts=1).build("demo")


def test_validator_exception_not_treated_as_repairable(tmp_path):
    def broken(_):
        raise RuntimeError("checker unavailable")
    with pytest.raises(RuntimeError):
        factory(tmp_path, broken, attempts=1).build("demo")


def test_contract_change_during_acceptance_stops_repairs(tmp_path):
    def validator(workspace):
        (workspace / "agent_spec.json").write_text("{}")
        return []
    result = factory(tmp_path, validator, attempts=2).build("demo")
    assert result.status == "failed"
    assert result.repair_attempts == 0
