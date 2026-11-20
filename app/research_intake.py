"""Deterministic intake gate for research-agent builds.

The model still formalizes the scientific contract.  This module provides the
cheap, auditable first gate used by the HTTP API and by fallback planning: a
factory build may not start from a generic request such as "make an agent".
"""

from dataclasses import asdict, dataclass
import re


_RELATION_TERMS = {
    "affect", "associate", "compare", "contrast", "difference", "effect", "estimate",
    "evaluate", "explain", "impact", "influence", "optimize", "predict", "relationship",
    "whether", "which", "why", "how", "does", "do", "versus", "vs",
    "afeta", "associação", "comparar", "diferença", "efeito", "estimar", "avaliar",
    "explicar", "impacto", "influência", "otimizar", "prever", "relação", "se", "como",
    "porquê", "qual", "quais",
}
_GENERIC_AGENT_TERMS = {
    "agent", "agente", "assistant", "assistente", "build", "create", "criar", "factory",
    "help", "research", "investigação", "pesquisa", "study", "estudo", "topic", "tema",
}
_STOPWORDS = {
    "a", "an", "and", "as", "at", "be", "for", "from", "in", "is", "it", "of", "on",
    "or", "that", "the", "this", "to", "with", "um", "uma", "e", "de", "do", "da",
    "dos", "das", "em", "no", "na", "nos", "nas", "o", "os", "que", "para", "por",
}


@dataclass(frozen=True)
class ResearchBriefStatus:
    ready: bool
    missing: tuple[str, ...]
    clarification: str
    meaningful_terms: int

    def to_dict(self) -> dict:
        return asdict(self)


def assess_research_brief(brief: str) -> ResearchBriefStatus:
    """Check whether a prompt contains a researchable relationship.

    This deliberately errs on the side of asking one more question.  The later
    structured ResearchQuestionSpec remains the authoritative scientific gate.
    """
    normalized = " ".join(str(brief).split()).strip()
    words = re.findall(r"[a-zA-ZÀ-ÿ][a-zA-ZÀ-ÿ0-9_-]*", normalized.casefold())
    meaningful = [word for word in words if word not in _STOPWORDS]
    domain_terms = [word for word in meaningful if word not in _GENERIC_AGENT_TERMS]
    has_relation = any(word in _RELATION_TERMS for word in meaningful)
    has_question_shape = "?" in normalized and len(domain_terms) >= 4
    ready = len(normalized) >= 35 and len(domain_terms) >= 5 and (has_relation or has_question_shape)
    if ready:
        return ResearchBriefStatus(True, (), "", len(domain_terms))
    if len(domain_terms) < 2:
        missing = ("topic", "research relationship", "scope")
        clarification = "What topic, population or system, outcome, and comparison should the agent investigate?"
    elif not has_relation and not has_question_shape:
        missing = ("research relationship",)
        clarification = "What exact relationship, effect, comparison or outcome should the research test?"
    else:
        missing = ("scope",)
        clarification = "Which population, dataset, period or setting should bound this research question?"
    return ResearchBriefStatus(False, missing, clarification, len(domain_terms))


def compile_research_brief(project_question: str, messages: list[dict], override: str | None = None) -> str:
    """Combine the initial topic and the user's intake answers without duplication."""
    override = (override or "").strip()
    parts: list[str] = [override or project_question.strip()]
    for message in messages[-12:]:
        if message.get("role") != "user":
            continue
        value = str(message.get("content", "")).strip()
        if value and not any(value == existing or value in existing for existing in parts):
            parts.append(value)
    return "\n\n".join(parts)[:10000]
