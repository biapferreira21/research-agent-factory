import app.planning.capability_planner as cp

from app.schemas.agent import AgentSpec, ModelSpec, ToolSpec
from app.schemas.capability import (CapabilitySpec, RequiredCapabilitySpec)



def test_plan_capabilities_returns_structured_response(
    monkeypatch,
):
    agent_spec = AgentSpec(
        name="file_agent",
        description="Agent for reading files",
        objective="Read files safely",
        inputs=["file_path"],
        outputs=["file_content"],
        architecture="single_agent",
        model=ModelSpec(
            provider="openai",
            model="test-model",
        ),
        system_prompt="Read files safely.",
    )

    expected = CapabilitySpec(
    agent_name="file_agent",
    capabilities=[
        RequiredCapabilitySpec(
            name="file_read",
            description="Read files from the authorized workspace",
        )
    ],
    )
    
    captured = {}

    class FakeCapabilityPlanner:
        def invoke(self, payload):
            captured["payload"] = payload

            return {
                "structured_response": expected
            }

    monkeypatch.setattr(
        cp,
        "create_capability_planner",
        lambda: FakeCapabilityPlanner(),
    )

    result = cp.plan_capabilities(agent_spec)

    assert result == expected
    assert isinstance(result, CapabilitySpec)

    message = captured["payload"]["messages"][0][1]

    assert '"name": "file_agent"' in message


