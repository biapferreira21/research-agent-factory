"""Demonstra o harness com um builder falso e pytest real, sem usar APIs."""

from pathlib import Path

from app.builder.harness import BuilderHarness
from app.schemas.agent import AgentSpec, ModelSpec
from app.schemas.capability import CapabilitySpec, RequiredCapabilitySpec
from app.tools.filesystem import create_filesystem_tools


def offline_planner(requirement: str) -> AgentSpec:
    return AgentSpec(
        name="offline_demo",
        description="Exemplo didático do controlo do harness",
        objective=requirement,
        inputs=["nome"],
        outputs=["saudação"],
        architecture="workflow",
        model=ModelSpec(provider="openai", model="unused-offline"),
        system_prompt="Exemplo determinístico; não invoca modelos.",
    )


def offline_capability_planner(spec: AgentSpec) -> CapabilitySpec:
    return CapabilitySpec(
        agent_name=spec.name, memory=spec.memory, runtime=spec.runtime,
        capabilities=[RequiredCapabilitySpec(
            name=tool.name, description=tool.description, source=tool.source, required=tool.required,
        ) for tool in spec.tools],
    )


class OfflineBuilder:
    def __init__(self, workspace: Path):
        self.tools = {tool.name: tool for tool in create_filesystem_tools(workspace)}

    def invoke(self, payload: dict, *, config: dict) -> None:
        # Num builder real, o LLM escolhe as chamadas. Aqui são explícitas.
        self.tools["write_file"].invoke({
            "path": "agent.py",
            "content": 'def greet(name):\n    return f"Hello, {name}!"\n',
        })
        self.tools["write_file"].invoke({
            "path": "tests/test_agent.py",
            "content": (
                'from agent import greet\n\n'
                'def test_greet():\n'
                '    assert greet("Ada") == "Hello, Ada!"\n'
            ),
        })


if __name__ == "__main__":
    harness = BuilderHarness(planner=offline_planner, builder_factory=OfflineBuilder,
                             capability_planner=offline_capability_planner)
    result = harness.build("Criar uma função de saudação para estudar o harness.")
    print(f"Status: {result.status}")
    print(f"Workspace: {result.workspace}")
    print(f"Telemetria: {result.telemetry_path}")
    for error in result.errors:
        print(error)
