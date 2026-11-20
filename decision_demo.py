"""Exercício offline: escolha falsa, baixa confiança e fallback explícito."""

from decimal import Decimal

from app.config import get_model_registry_path
from app.decisions.backends import ConfiguredModelBackend, FixedDecisionBackend
from app.decisions.model_router import choice_id
from app.decisions.schemas import DecisionPolicy, DecisionRequest, DecisionState, ModelChoice
from app.decisions.service import DecisionBlocked, DecisionService
from app.registry.models import ModelRegistry, ModelRequirements


if __name__ == "__main__":
    registry = ModelRegistry.load(get_model_registry_path())
    candidates = registry.candidates(ModelRequirements(tool_calling=True, allow_router=True, max_reservation_usd=Decimal("1")))
    request = DecisionRequest(
        state=DecisionState(stage="demo", preferred_choice_id="openrouter:openrouter/free", remaining_budget_usd=Decimal("1")),
        candidates=tuple(ModelChoice(
            id=choice_id(entry), provider=entry.provider, model=entry.model,
            reservation_usd=entry.reservation(), context_window=entry.context_window,
            tool_calling=entry.tool_calling, structured_output=entry.structured_output,
        ) for entry in candidates),
    )
    fake = FixedDecisionBackend("openrouter:openrouter/free", confidence=0.40)
    print("Decisor falso com confiança 0.40; política exige 0.80:")
    try:
        DecisionService(fake).decide(request)
    except DecisionBlocked as error:
        print(f"Bloqueado: {error}")

    print("\nAgora com fallback explícito para a regra do modelo configurado:")
    service = DecisionService(fake, policy=DecisionPolicy(on_low_confidence="fallback"),
                              fallback=ConfiguredModelBackend())
    records = []
    try:
        result = service.decide(request, sink=records.append)
        print(result.model_dump_json(indent=2))
    except DecisionBlocked as error:
        print(f"Bloqueado: {error}")
    print(f"Tentativas registadas: {len(records)}")
    print("Nenhum modelo foi chamado; confiança 1.0 da regra significa apenas escolha determinística.")
