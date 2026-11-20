import app.tools.filesystem as fs
from app.tools.testing import run_pytest
from app.tools.testing import execute_pytest
import subprocess
import sys

def test_run_pytest_passes(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    fs.write_file.invoke(
        {
            "path": "demo/test_ok.py",
            "content": "def test_ok():\n    assert 2 + 2 == 4\n",
        }
    )

    result = run_pytest.invoke(
        {
            "project_path": "demo",
        }
    )

    assert "exit_code=0" in result
    assert "1 passed" in result


def test_run_pytest_reports_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    fs.write_file.invoke(
        {
            "path": "demo/test_fail.py",
            "content": "def test_fail():\n    assert 2 + 2 == 5\n",
        }
    )

    result = run_pytest.invoke(
        {
            "project_path": "demo",
        }
    )

    assert "exit_code=1" in result
    assert "1 failed" in result


def test_long_output_preserves_exit_code_and_working_directory(tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        assert command == [sys.executable, "-m", "pytest", "."]
        assert kwargs["cwd"] == tmp_path.resolve()
        return subprocess.CompletedProcess(command, 0, "x" * 30000, "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = execute_pytest(tmp_path)
    assert result.passed
    assert len(result.output) == 20000
    assert result.as_text().startswith("exit_code=0\n")


def test_timeout_is_not_success(tmp_path, monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, 120)

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = execute_pytest(tmp_path)
    assert result.timed_out
    assert not result.passed

    
