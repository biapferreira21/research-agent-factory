"""Demonstração instalada: modelos falsos, código gerado determinístico, pytest real."""
from pathlib import Path

from app.builder.harness import BuilderHarness
from app.schemas.agent import AgentSpec, EvaluationSpec, ModelSpec
from app.schemas.capability import CapabilitySpec
from app.schemas.research import ResearchProtocol, ResearchQuestionSpec, ResearchMetric, SuccessCriterion
from app.tools.filesystem import create_filesystem_tools


def protocol():
    return ResearchProtocol(
        question=ResearchQuestionSpec(question="Compare A and B in a teaching example", domain="didactic",
                                     hypothesis="A reduces mean error", inputs=["synthetic dataset v1"]),
        method="Compare A and B across the stated seeds", baselines=["B"],
        metrics=[ResearchMetric(name="error", direction="minimize", measurement="Error per seed")],
        seeds=[11, 22, 33], success_criteria="At least 5% mean improvement",
        executable_criteria=[SuccessCriterion(metric="error", baseline="B", min_relative_improvement="0.05")],
        stopping_rule="One measurement per method and seed", provenance_policy="Record versions and parameters",
        limitations=["Synthetic demonstration; does not validate a scientific hypothesis"])


def planner(requirement):
    return AgentSpec(name="offline_demo", description="Deterministic demonstration",
                     objective=requirement, inputs=["name"], outputs=["greeting"], architecture="workflow",
                     model=ModelSpec(provider="openrouter", model="unused-offline"),
                     system_prompt="Deterministic greeting function; do not call models.",
                     evaluations=[EvaluationSpec(name="greeting", description="Check greeting",
                                                 success_criteria="greet('Ada') returns Hello, Ada!")])


def capability_planner(spec):
    return CapabilitySpec(agent_name=spec.name, memory=spec.memory, runtime=spec.runtime, capabilities=[])


class DemoBuilder:
    def __init__(self, workspace: Path):
        self.tools = {tool.name: tool for tool in create_filesystem_tools(workspace)}

    def invoke(self, payload, *, config):
        contents = {
            "agent.py": 'def greet(name):\n    return f"Hello, {name}!"\n',
            "tests/test_agent.py": 'from agent import greet\n\ndef test_greet():\n    assert greet("Ada") == "Hello, Ada!"\n',
            "README.md": "# Offline demo\nDeterministic greeting. No research experiments executed.\n",
        }
        for path, content in contents.items():
            self.tools["write_file"].invoke({"path": path, "content": content})


def run(root: Path):
    """Exercitar pipeline científico e arquivo associado, sem API nem dados reais."""
    from app.planning.build_evaluation import archive_build_results
    from app.planning.research_validation import protocol_digest
    from app.schemas.results import ExperimentResults, Measurement
    planned = protocol()
    harness = BuilderHarness(root=root, planner=planner, builder_factory=DemoBuilder,
                             capability_planner=capability_planner,
                             research_planner=lambda _: planned,
                             scientific_architect=lambda p: planner(p.question.question))
    result = harness.build_research(planned.question)
    if result.status != "passed":
        return {"build": result.to_dict(), "evaluation_archive": None}
    results = ExperimentResults(protocol_sha256=protocol_digest(planned), origin="synthetic",
                                candidate_method="A", code_version="demo-v1", dataset_version="synthetic-v1",
                                parameters_json='{"demo": true}', measurements=tuple(
                                    Measurement(method=method, metric="error", seed=seed, value=value)
                                    for method, value in (("A", 0.8), ("B", 1.0)) for seed in planned.seeds))
    archive = archive_build_results(root, result.build_id, results)
    return {"build": result.to_dict(), "evaluation_archive": str(archive)}
