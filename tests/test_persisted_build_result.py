import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.telemetry.costs import BudgetBlocked
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def harness(tmp_path, **kwargs):
    return BuilderHarness(root=tmp_path, event_sink=None,
                          builder_factory=OfflineBuilder, capability_planner=offline_capability_planner, **kwargs)


@pytest.mark.parametrize("exit_code,status", [(0, "passed"), (1, "failed")])
def test_result_matches_return_value(tmp_path, exit_code, status):
    result = harness(tmp_path, planner=offline_planner,
                     test_runner=lambda _: PytestResult(exit_code, "test output")).build("demo")
    path = Path(result.telemetry_path) / "build_result.json"
    assert json.loads(path.read_text(encoding="utf-8")) == result.to_dict()
    assert result.status == status
    assert not path.with_suffix(".json.tmp").exists()


def test_blocked_before_workspace_saved(tmp_path):
    def blocked(_):
        raise BudgetBlocked("Budget exhausted")
    result = harness(tmp_path, planner=blocked).build("demo")
    data = json.loads((Path(result.telemetry_path) / "build_result.json").read_text())
    assert data["status"] == "blocked"
    assert data["workspace"] == ""


def test_unexpected_failure_saved_but_still_raised(tmp_path):
    def failing(_):
        raise RuntimeError("SECRET")
    with pytest.raises(RuntimeError, match="SECRET"):
        harness(tmp_path, planner=failing).build("demo")
    path = next(tmp_path.glob(".factory_runs/*/build_result.json"))
    data = json.loads(path.read_text())
    assert data["status"] == "failed"
    assert data["errors"] == ["Unexpected failure: RuntimeError"]
    assert "SECRET" not in path.read_text()
