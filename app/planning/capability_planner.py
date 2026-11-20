from langchain.agents import create_agent


from app.models import get_model
from app.planning.capability_prompt import CAPABILITY_PLANNER_PROMPT
from app.schemas.agent import AgentSpec
from app.schemas.capability import CapabilitySpec

def create_capability_planner():
    return create_agent(
        model=get_model(structured_output=True),
        tools=[],
        system_prompt=CAPABILITY_PLANNER_PROMPT,
        response_format=CapabilitySpec,
    )

def plan_capabilities(agent_spec: AgentSpec) -> CapabilitySpec:
    result = create_capability_planner().invoke(
        {
            "messages": [
                (
                    "user",
                    (
                        "Analyze the approved AgentSpec below and produce "
                        "the required CapabilitySpec.\n\n"
                        f"{agent_spec.model_dump_json(indent=2)}"
                    ),
                )
            ]
        }
    )

    return result["structured_response"]


