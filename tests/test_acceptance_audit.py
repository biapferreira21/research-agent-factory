import hashlib
import json
from pathlib import Path

import pytest

from app.builder.harness import BuilderHarness
from app.tools.acceptance import AcceptanceExecutionError, PythonAcceptance
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def factory(tmp_path, validator):
    return BuilderHarness(root=tmp_path / "builds", acceptance_validator=validator,
                          planner=offline_planner, capability_planner=offline_capability_planner,
                          builder_factory=OfflineBuilder, test_runner=lambda _: PytestResult(0, "ok"),
                          event_sink=None)


def test_script_identity_saved_with_result(tmp_path):
    script = tmp_path / "check.py"
    script.write_text('print(\'{"errors": []}\')')
    validator = PythonAcceptance(script, timeout_seconds=7)
    result = factory(tmp_path, validator).build("demo")
    record = json.loads((Path(result.telemetry_path) / "acceptance.jsonl").read_text())
    assert record["passed"]
    assert record["validator"]["script_sha256"] == hashlib.sha256(script.read_bytes()).hexdigest()
    assert record["validator"]["timeout_seconds"] == 7


def test_crash_recorded_without_raw_error(tmp_path):
    def validator(_):
        raise RuntimeError("SECRET")
    with pytest.raises(RuntimeError):
        factory(tmp_path, validator).build("demo")
    log = next((tmp_path / "builds").glob(".factory_runs/*/acceptance.jsonl"))
    record = json.loads(log.read_text())
    assert record["status"] == "execution_error"
    assert record["error_type"] == "RuntimeError"
    assert record["validator"]["version_verified"] is False
    assert "SECRET" not in log.read_text()


def test_changed_script_records_expected_hash(tmp_path):
    script = tmp_path / "check.py"
    script.write_text('print(\'{"errors": []}\')')
    validator = PythonAcceptance(script)
    expected = validator.sha256
    script.write_text("raise RuntimeError()")
    with pytest.raises(AcceptanceExecutionError):
        factory(tmp_path, validator).build("demo")
    log = next((tmp_path / "builds").glob(".factory_runs/*/acceptance.jsonl"))
    record = json.loads(log.read_text())
    assert record["validator"]["script_sha256"] == expected
    assert record["passed"] is False
