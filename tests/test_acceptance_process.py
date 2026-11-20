import subprocess

import pytest

from app.tools.acceptance import AcceptanceExecutionError, PythonAcceptance


def checker(tmp_path, source, **kwargs):
    script = tmp_path / "check.py"
    script.write_text(source, encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    return PythonAcceptance(script, **kwargs), workspace


def test_real_process_reports_missing_requirement_then_passes(tmp_path):
    validator, workspace = checker(tmp_path,
        'import json, sys\nfrom pathlib import Path\n'
        'print(json.dumps({"errors": [] if (Path(sys.argv[1])/"README.md").exists() else ["missing"]}))')
    assert validator(workspace) == ["missing"]
    (workspace / "README.md").write_text("hello")
    assert validator(workspace) == []


@pytest.mark.parametrize("source", ['print("not json")', 'print("[]")',
                                    'print(\'{"errors": [1]}\')', 'raise RuntimeError("secret")'])
def test_invalid_response_or_crash_is_infrastructure_failure(tmp_path, source):
    validator, workspace = checker(tmp_path, source)
    with pytest.raises(AcceptanceExecutionError) as error:
        validator(workspace)
    assert "secret" not in str(error.value)


def test_timeout_is_not_a_repairable_error_list(tmp_path, monkeypatch):
    validator, workspace = checker(tmp_path, 'print(\'{"errors": []}\')')
    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == 30
        assert args[0][1] == "-I"
        raise subprocess.TimeoutExpired("python", 30)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(AcceptanceExecutionError, match="Timeout"):
        validator(workspace)


def test_modified_script_rejected_before_execution(tmp_path):
    validator, workspace = checker(tmp_path, 'print(\'{"errors": []}\')')
    validator.script.write_text('print("modified")')
    with pytest.raises(AcceptanceExecutionError, match="mudou"):
        validator(workspace)


def test_script_inside_generated_workspace_rejected(tmp_path):
    validator, workspace = checker(tmp_path, 'print(\'{"errors": []}\')')
    with pytest.raises(AcceptanceExecutionError, match="fora"):
        validator(tmp_path)
