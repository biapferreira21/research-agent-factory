"""Verificações determinísticas; não substituem revisão científica."""

import hashlib
import json

from app.schemas.research import ResearchProtocol, ResearchQuestionSpec


class ResearchPlanningBlocked(RuntimeError):
    pass


_USER_ONLY_TERMS = (
    "private dataset", "proprietary dataset", "restricted dataset", "dataset access",
    "data access", "access permission", "credentials", "api key", "consent",
    "legal approval", "ethics approval", "required file", "upload", "file path",
    "what topic", "which topic", "which population", "what population",
    "which outcome", "what outcome", "which comparison", "what comparison",
    "which domain", "what domain", "time period", "geographic scope",
    "dataset privado", "dados privados", "dados proprietários", "credenciais",
    "chave de api", "consentimento", "aprovação ética", "ficheiro obrigatório",
    "carregar ficheiro", "qual população", "qual resultado", "qual comparação",
    "qual domínio", "período temporal", "âmbito geográfico",
)


def resolve_factory_design_questions(question: ResearchQuestionSpec) -> list[str]:
    """Turn delegated research-design choices into explicit assumptions.

    A research agent should stop for information only the user can supply. The
    factory itself can propose a benchmark, rubric, logging schema or bounded
    optimization policy and mark that proposal for validation before results
    are treated as evidence.
    """
    delegated, unresolved = [], []
    for item in question.open_questions:
        lowered = " ".join(item.casefold().split())
        requires_user = any(term in lowered for term in _USER_ONLY_TERMS)
        # A validated live brief already supplies a researchable topic and
        # relationship. Unless the question asks for unavailable user data or
        # scope, the factory owns the remaining methodological choice.
        (unresolved if requires_user else delegated).append(item)
    if delegated:
        existing = set(question.assumptions)
        additions = [
            "Factory design assumption, to validate before empirical use: " + item
            for item in delegated
        ]
        question.assumptions.extend(item for item in additions if item not in existing)
        question.open_questions = unresolved
    return delegated


def require_answered_question(question: ResearchQuestionSpec) -> None:
    if question.open_questions:
        raise ResearchPlanningBlocked("Falta esclarecer a pergunta: " + "; ".join(question.open_questions))


def validate_research_protocol(question: ResearchQuestionSpec, protocol: ResearchProtocol) -> None:
    if protocol.question != question:
        raise ResearchPlanningBlocked("O ResearchPlanner alterou a pergunta científica ou as suas restrições.")
    if protocol.open_questions:
        raise ResearchPlanningBlocked("Falta esclarecer o protocolo: " + "; ".join(protocol.open_questions))


def protocol_digest(protocol: ResearchProtocol) -> str:
    # Ordenar as chaves torna o identificador independente da formatação do JSON.
    canonical = json.dumps(protocol.model_dump(mode="json"), sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
