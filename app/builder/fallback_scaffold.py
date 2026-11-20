"""Create a small, valid research agent when model-generated code cannot pass validation."""
from pathlib import Path
import shutil


AGENT_SOURCE = '''"""Executable research-agent scaffold generated from approved factory contracts."""
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parent


def _contract(name: str) -> dict:
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


@dataclass(frozen=True)
class ResearchAgent:
    """A contract-bound agent that prepares reproducible research work."""

    spec: dict
    protocol: dict
    capabilities: dict

    @classmethod
    def from_contracts(cls) -> "ResearchAgent":
        return cls(_contract("agent_spec.json"), _contract("research_protocol.json"),
                   _contract("capability_spec.json"))

    def prepare(self, query: str, evidence: Iterable[str] = ()) -> dict:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("A non-empty research query is required")
        sources = [str(item).strip() for item in evidence if str(item).strip()]
        question = self.protocol["question"]["question"]
        return {
            "agent": self.spec["name"],
            "objective": self.spec["objective"],
            "research_question": question,
            "query": query.strip(),
            "method": self.protocol["method"],
            "metrics": self.protocol["metrics"],
            "seeds": self.protocol["seeds"],
            "evidence": sources,
            "status": "ready_for_analysis" if sources else "needs_evidence",
            "limitations": self.protocol.get("limitations", []),
            "provenance_policy": self.protocol["provenance_policy"],
        }


def create_agent() -> ResearchAgent:
    return ResearchAgent.from_contracts()


if __name__ == "__main__":
    print(json.dumps(create_agent().prepare("Prepare the next research step"), indent=2))
'''


TEST_SOURCE = '''from agent import create_agent


def test_agent_loads_the_approved_contracts():
    agent = create_agent()
    plan = agent.prepare("Compare the approved methods", ["source:1"])
    assert plan["agent"] == agent.spec["name"]
    assert plan["research_question"] == agent.protocol["question"]["question"]
    assert plan["status"] == "ready_for_analysis"
    assert plan["evidence"] == ["source:1"]


def test_agent_does_not_claim_results_without_evidence():
    plan = create_agent().prepare("Plan the analysis")
    assert plan["status"] == "needs_evidence"
    assert plan["evidence"] == []
'''


README_SOURCE = '''# Validated research agent

This Python agent is a deterministic fallback produced after the model-generated implementation did not pass the factory gates. It remains specific to this build because it loads the approved research question, protocol, agent specification, capability plan, MCP selection and runtime configuration stored beside the code.

Run `python agent.py` to inspect the next research step or import `create_agent` from `agent.py`. The scaffold prepares work and preserves provenance; it does not invent measurements or claim that experiments ran.
'''


def write_research_scaffold(workspace: Path, contracts: dict[str, str]) -> None:
    """Replace invalid generated code while preserving all approved contracts exactly."""
    root = workspace.resolve(strict=True)
    for child in root.iterdir():
        if child.name in contracts:
            continue
        if child.is_symlink():
            child.unlink()
            continue
        resolved = child.resolve()
        if not resolved.is_relative_to(root):
            raise ValueError("Generated artifact is outside the build workspace")
        if child.is_file():
            child.unlink()
        elif child.is_dir():
            shutil.rmtree(child)
    for name, content in contracts.items():
        (root / name).write_text(content, encoding="utf-8")
    (root / "agent.py").write_text(AGENT_SOURCE, encoding="utf-8")
    tests = root / "tests"
    tests.mkdir()
    (tests / "test_agent.py").write_text(TEST_SOURCE, encoding="utf-8")
    (root / "README.md").write_text(README_SOURCE, encoding="utf-8")
