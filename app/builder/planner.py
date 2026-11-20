from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.config import get_settings
from app.models import get_model
from app.schemas.agent import AgentSpec, ModelSpec
from app.builder.prompt import PLANNER_PROMPT
from app.registry.runtime import get_registry, require_model
from app.registry.models import ModelRequirements
from app.retrieval.context import evidence_messages


def create_planner_agent():
    """Importar este módulo não cria clientes nem exige API keys."""
    return create_agent(
        model=get_model(),
        tools=[],
        system_prompt=PLANNER_PROMPT,
        response_format=ToolStrategy(AgentSpec),
    )

def create_agent_spec(requirement: str) -> AgentSpec:
    settings = get_settings()
    from app.telemetry.build import active_build
    telemetry = active_build.get()
    selected_provider = telemetry.model_provider if telemetry and telemetry.model_provider else settings.model_provider
    selected_model = telemetry.model if telemetry and telemetry.model else (
        settings.openrouter_model if selected_provider == "openrouter" else settings.openai_model)
    candidates = get_registry().candidates(ModelRequirements(allow_router=settings.allow_model_router))
    approved_models = "\n".join(f"- {entry.provider}: {entry.model}" for entry in candidates)

    planning_request = f"""
User requirement:
{requirement}

Selected model for this build and the resulting agent:
- provider: {selected_provider}
- model: {selected_model}

Use this exact selected model.
Choose the runtime model only from this approved catalog:
{approved_models}
"""

    result = create_planner_agent().invoke(
        {
            "messages": evidence_messages() + [
                {
                    "role": "user",
                    "content": planning_request,
                }
            ]
        }
    )

    spec = result["structured_response"]
    spec.model = ModelSpec(provider=selected_provider, model=selected_model)
    require_model(spec.model.provider, spec.model.model, tool_calling=bool(spec.tools))
    return spec

