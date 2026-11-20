from app.builder.planner import create_agent_spec
from app.planning.research_prompt import SCIENTIFIC_ARCHITECT_INSTRUCTIONS
from app.planning.research_validation import require_answered_question, validate_research_protocol
from app.schemas.agent import AgentSpec
from app.schemas.research import ResearchProtocol


def create_scientific_agent_spec(protocol: ResearchProtocol) -> AgentSpec:
    protocol = ResearchProtocol.model_validate(protocol.model_dump())
    require_answered_question(protocol.question)
    validate_research_protocol(protocol.question, protocol)
    # Reutiliza o architect base, incluindo a validação do catálogo de modelos.
    return create_agent_spec(
        SCIENTIFIC_ARCHITECT_INSTRUCTIONS + "\nResearchProtocol:\n" + protocol.model_dump_json(indent=2)
    )
