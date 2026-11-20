from decimal import Decimal

from app.config import get_settings
from app.decisions.backends import ConfiguredModelBackend
from app.decisions.schemas import DecisionRequest, DecisionState, ModelChoice
from app.decisions.service import DecisionBlocked, DecisionService
from app.registry.models import ModelRequirements, RegisteredModel
from app.registry.runtime import get_registry, require_model
from app.telemetry.build import active_build
from app.telemetry.costs import BudgetBlocked


def choice_id(entry: RegisteredModel) -> str:
    return f"{entry.provider}:{entry.model}"


def route_model(provider: str, model: str, *, tool_calling: bool, structured_output: bool) -> RegisteredModel:
    telemetry = active_build.get()
    if telemetry is None:
        return require_model(provider, model, tool_calling=tool_calling, structured_output=structured_output)
    costs = telemetry.tracker.summary()
    if costs.over_budget:
        raise BudgetBlocked("O orçamento já foi ultrapassado; routing bloqueado.")
    if costs.budget_usd is not None and costs.unknown_calls:
        raise BudgetBlocked("Existe custo desconhecido; routing bloqueado.")
    requirements = ModelRequirements(
        provider=provider, tool_calling=tool_calling, structured_output=structured_output,
        allow_router=get_settings().allow_model_router, max_reservation_usd=costs.remaining_usd,
    )
    registry = get_registry()
    manual_reservation = telemetry.call_reservation_usd or Decimal("0")
    candidates = [entry for entry in registry.candidates(requirements)
                  if costs.remaining_usd is None or max(entry.reservation(), manual_reservation) <= costs.remaining_usd]
    request = DecisionRequest(
        state=DecisionState(stage=telemetry.current_stage.value, preferred_choice_id=f"{provider}:{model}",
                            remaining_budget_usd=costs.remaining_usd,
                            research_protocol_sha256=telemetry.research_protocol_sha256),
        candidates=tuple(ModelChoice(
            id=choice_id(entry), provider=entry.provider, model=entry.model,
            reservation_usd=max(entry.reservation(), manual_reservation), context_window=entry.context_window,
            tool_calling=entry.tool_calling, structured_output=entry.structured_output,
        ) for entry in candidates),
    )
    service = telemetry.decision_service if telemetry.decision_service is not None else DecisionService(ConfiguredModelBackend())
    result = service.decide(request, sink=telemetry.record_decision)
    # Revalidar depois da decisão: o saldo e a validade dos preços podem ter mudado.
    chosen = next(entry for entry in candidates if choice_id(entry) == result.choice_id)
    fresh_costs = telemetry.tracker.summary()
    if fresh_costs.over_budget:
        raise BudgetBlocked("O orçamento foi ultrapassado durante a decisão.")
    if fresh_costs.budget_usd is not None and fresh_costs.unknown_calls:
        raise BudgetBlocked("O custo tornou-se desconhecido durante a decisão.")
    eligible = registry.candidates(ModelRequirements(
        provider=provider, tool_calling=tool_calling, structured_output=structured_output,
        allow_router=get_settings().allow_model_router, max_reservation_usd=fresh_costs.remaining_usd,
    ))
    if chosen not in eligible or (fresh_costs.remaining_usd is not None
                                 and max(chosen.reservation(), manual_reservation) > fresh_costs.remaining_usd):
        raise DecisionBlocked("O modelo deixou de ser elegível depois da decisão.")
    return chosen
