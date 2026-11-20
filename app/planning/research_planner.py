from langchain.agents import create_agent
from langchain.agents.structured_output import ToolStrategy

from app.models import get_model
from app.planning.research_prompt import PROTOCOL_PROMPT, QUESTION_PROMPT
from app.planning.research_validation import require_answered_question, validate_research_protocol
from app.schemas.research import ResearchProtocol, ResearchQuestionSpec
from app.retrieval.context import evidence_messages


def create_question_formalizer():
    return create_agent(model=get_model(), tools=[], system_prompt=QUESTION_PROMPT,
                        response_format=ToolStrategy(ResearchQuestionSpec))


def create_research_planner():
    return create_agent(model=get_model(), tools=[], system_prompt=PROTOCOL_PROMPT,
                        response_format=ToolStrategy(ResearchProtocol))


def formalize_research_question(request: str) -> ResearchQuestionSpec:
    if not request.strip():
        raise ValueError("A pergunta de investigação não pode estar vazia.")
    result = create_question_formalizer().invoke({"messages": evidence_messages() + [{"role": "user", "content": request}]})
    return ResearchQuestionSpec.model_validate(result["structured_response"].model_dump())


def create_research_protocol(question: ResearchQuestionSpec) -> ResearchProtocol:
    question = ResearchQuestionSpec.model_validate(question.model_dump())
    require_answered_question(question)
    result = create_research_planner().invoke({
        "messages": evidence_messages() + [{"role": "user", "content": question.model_dump_json(indent=2)}],
    })
    protocol = ResearchProtocol.model_validate(result["structured_response"].model_dump())
    validate_research_protocol(question, protocol)
    return protocol
