from pathlib import Path

import pytest
from pydantic import ValidationError

from app.builder.harness import BuilderHarness
from app.tools.testing import PytestResult
from harness_offline_demo import OfflineBuilder, offline_planner, offline_capability_planner


def test_offline_build_runs_real_tests(tmp_path):
    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
    ).build("Say hello")
    assert result.status == "passed", result.errors
    assert (Path(result.workspace) / "agent_spec.json").is_file()


def test_failed_tests_fail_the_build(tmp_path):
    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
        test_runner=lambda path: PytestResult(1, "assertion failed"),
    ).build("Say hello")
    assert result.status == "failed"
    assert "assertion failed" in result.errors[0]


def test_gates_prevent_test_execution(tmp_path):
    class EmptyBuilder:
        def __init__(self, workspace):
            pass

        def invoke(self, payload, *, config):
            pass

    def forbidden_runner(path):
        pytest.fail("pytest must not run when gates fail")

    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=EmptyBuilder,
        test_runner=forbidden_runner,
    ).build("Say hello")
    assert result.status == "failed"
    assert "Missing required directory: tests" in result.errors


@pytest.mark.parametrize("name", ["../escape", "C:/escape", "bad/name", "con", "lpt1", "name.", ""])
def test_invalid_name_is_rejected_before_writing(tmp_path, name):
    def planner(requirement):
        spec = offline_planner(requirement)
        spec.name = name  # Mesmo uma instância alterada tem de ser revalidada.
        return spec

    with pytest.raises(ValidationError):
        BuilderHarness(capability_planner=offline_capability_planner, root=tmp_path, planner=planner).build("Say hello")
    assert [path.name for path in tmp_path.iterdir()] == [".factory_runs"]


def test_spec_tampering_prevents_validation(tmp_path):
    class TamperingBuilder(OfflineBuilder):
        def __init__(self, workspace):
            self.workspace = workspace

        def invoke(self, payload, *, config):
            (self.workspace / "agent_spec.json").write_text("{}", encoding="utf-8")

    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=TamperingBuilder,
        test_runner=lambda path: pytest.fail("Must not execute altered build"),
    ).build("Say hello")
    assert result.status == "failed"
    assert "modified or removed" in result.errors[0]


def test_spec_tampering_during_tests_is_detected(tmp_path):
    def runner(workspace):
        (workspace / "agent_spec.json").write_text("{}", encoding="utf-8")
        return PytestResult(0, "passed")

    result = BuilderHarness(capability_planner=offline_capability_planner, 
        root=tmp_path, planner=offline_planner, builder_factory=OfflineBuilder,
        test_runner=runner,
    ).build("Say hello")
    assert result.status == "failed"
    assert "during validation" in result.errors[0]


def test_empty_requirement_does_not_call_planner(tmp_path):
    with pytest.raises(ValueError, match="vazio"):
        BuilderHarness(capability_planner=offline_capability_planner, root=tmp_path, planner=lambda _: pytest.fail("Planner called")).build("  ")
