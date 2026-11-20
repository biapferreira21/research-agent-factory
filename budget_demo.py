"""Estudar reservas com custos fictícios. Não chama modelos nem gasta dinheiro."""

from decimal import Decimal

from app.telemetry.costs import BudgetBlocked, CostTracker
from app.telemetry.schemas import BuildStage, UsageRecord


if __name__ == "__main__":
    tracker = CostTracker(budget_usd=Decimal("1.00"))
    tracker.reserve("example-call", Decimal("0.60"))
    print("Depois de reservar USD 0.60:")
    print(tracker.summary().model_dump_json(indent=2))

    # Simular uma resposta que custou menos do que a reserva.
    tracker.settle(UsageRecord(
        call_id="example-call", stage=BuildStage.PLANNING,
        provider="simulated", model="simulated", status="succeeded",
        input_tokens=100, output_tokens=50, duration_seconds=0,
        reservation_usd=Decimal("0.60"), actual_cost_usd=Decimal("0.25"),
    ))
    print("\nDepois do custo fictício de USD 0.25:")
    print(tracker.summary().model_dump_json(indent=2))

    try:
        tracker.reserve("too-expensive", Decimal("0.80"))
    except BudgetBlocked as error:
        print(f"\nBloqueado: {error}")
