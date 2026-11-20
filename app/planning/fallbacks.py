"""Deterministic contracts used when a free router returns malformed structured output."""
import re

from app.config import get_settings
from app.schemas.agent import AgentSpec, EvaluationSpec, ModelSpec
from app.schemas.capability import CapabilitySpec, RequiredCapabilitySpec
from app.schemas.research import ResearchMetric, ResearchProtocol, ResearchQuestionSpec


def is_response_validation_error(error: BaseException) -> bool:
    current: BaseException | None = error
    while current is not None:
        if type(current).__name__ in {"ResponseValidationError", "StructuredOutputValidationError",
                                     "MultipleStructuredOutputsError"}:
            return True
        current = current.__cause__ or current.__context__
    return False


def fallback_question(request: str) -> ResearchQuestionSpec:
    from app.research_intake import assess_research_brief
    readiness = assess_research_brief(request)
    return ResearchQuestionSpec(
        question=request.strip(),
        domain="general research",
        hypothesis="The factors named in the research question produce measurable differences in the primary outcome.",
        inputs=["User-provided project documents and data"],
        constraints=["Use only traceable evidence and report missing data"],
        assumptions=["The user will provide the data required for empirical claims"],
        open_questions=[] if readiness.ready else list(readiness.missing),
    )


def fallback_protocol(question: ResearchQuestionSpec) -> ResearchProtocol:
    return ResearchProtocol(
        question=question,
        method=("Run a reproducible comparative analysis that operationalizes the hypothesis, "
                "holds evaluation conditions constant, and reports uncertainty."),
        baselines=["Reference method or current practice"],
        metrics=[ResearchMetric(name="primary_outcome", direction="maximize",
                                measurement="Predeclared primary outcome measured identically for every method")],
        seeds=[11, 22, 33],
        success_criteria="Report the primary outcome and uncertainty for every method and baseline.",
        stopping_rule="Stop after all predeclared methods, baselines, and seeds have valid measurements.",
        provenance_policy="Record source identifiers, dataset versions, parameters, code version, and random seeds.",
        limitations=["This fallback protocol requires domain review before results are treated as scientific evidence"],
        assumptions=list(question.assumptions),
    )


def fallback_agent_spec(protocol: ResearchProtocol) -> AgentSpec:
    settings = get_settings()
    words = [word[:14] for word in re.findall(r"[a-z0-9]+", protocol.question.domain.lower())[:4]]
    name = "_".join(words + ["research_agent"]) if words else "general_research_agent"
    from app.telemetry.build import active_build
    telemetry = active_build.get()
    provider = telemetry.model_provider if telemetry and telemetry.model_provider else settings.model_provider
    model = telemetry.model if telemetry and telemetry.model else (
        settings.openrouter_model if provider == "openrouter" else settings.openai_model)
    return AgentSpec(
        name=name[:80].rstrip("_"),
        description="Research agent generated from a validated scientific protocol.",
        objective=protocol.question.question,
        inputs=list(protocol.question.inputs),
        outputs=["Evidence-grounded research report", "Reproducible analysis artifacts"],
        architecture="workflow",
        model=ModelSpec(provider=provider, model=model),
        system_prompt=("Follow the approved research protocol exactly. Cite project evidence, distinguish findings from "
                       "assumptions, preserve provenance, and never invent measurements or completed experiments."),
        evaluations=[EvaluationSpec(name="protocol_compliance", description="Check outputs against the approved protocol",
                                    success_criteria="All claims are traceable and all protocol requirements are addressed")],
        assumptions=list(protocol.assumptions),
        risks=["Insufficient project evidence", "Domain-specific protocol details may require human review"],
    )


def fallback_capabilities(spec: AgentSpec) -> CapabilitySpec:
    return CapabilitySpec(
        agent_name=spec.name,
        memory=spec.memory,
        runtime=spec.runtime,
        capabilities=[RequiredCapabilitySpec(
            name=tool.name,
            description=tool.description,
            required=tool.required,
            source=tool.source,
        ) for tool in spec.tools],
        constraints=["Use only project-scoped files and approved runtime tools"],
    )
