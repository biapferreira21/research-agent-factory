"""Exercita o adaptador HTTP sem rede, credenciais reais ou cobrança."""
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx

from app.decisions.jev import JevBackend
from app.decisions.schemas import DecisionRequest, DecisionState, ModelChoice
from app.decisions.service import DecisionService
from app.telemetry.build import BuildTelemetry


def main():
    def fake_server(request):
        return httpx.Response(200, json={
            "answers": {"route": {"type": "choice", "choice": "free", "confidence": 1.0,
                                   "probabilities": {"free": 1.0}}},
            "usage": {"cost": 0.000014994},
        })

    run_id = str(uuid4())
    directory = Path(__file__).resolve().parent / "generated_agents" / ".jev_demos" / run_id
    telemetry = BuildTelemetry(run_id, directory, Decimal("1.00"), sink=None)
    service = DecisionService(JevBackend("fake-key", transport=httpx.MockTransport(fake_server)))
    request = DecisionRequest(
        state=DecisionState(stage="planning", preferred_choice_id="free"),
        candidates=(ModelChoice(id="free", provider="openrouter", model="openrouter/free",
                                reservation_usd=0, context_window=200000,
                                tool_calling=True, structured_output=True),),
    )
    with telemetry.activate():
        result = service.decide(request, sink=telemetry.record_decision)
    telemetry.finish("passed")
    print("SIMULACAO: nenhuma chamada externa ou cobranca.")
    print(result.model_dump_json(indent=2))
    print("Custo ficticio:", telemetry.tracker.summary().reported_cost_usd)
    print("Registos:", directory)


if __name__ == "__main__":
    main()
