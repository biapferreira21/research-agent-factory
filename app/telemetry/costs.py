"""Reservar antes de executar; reconciliar sem esconder custos desconhecidos."""

from decimal import Decimal
from threading import RLock

from app.telemetry.schemas import CostSummary, UsageRecord


class BudgetBlocked(RuntimeError):
    pass


def money(value: Decimal | str | int) -> Decimal:
    amount = Decimal(str(value))
    if not amount.is_finite() or amount < 0:
        raise ValueError("O custo tem de ser finito e não negativo.")
    return amount


class CostTracker:
    def __init__(self, budget_usd: Decimal | None = None):
        self.budget_usd = None if budget_usd is None else money(budget_usd)
        self._pending: dict[str, Decimal | None] = {}
        self._records: dict[str, UsageRecord] = {}
        self._lock = RLock()

    def reserve(self, call_id: str, estimate_usd: Decimal | None) -> None:
        estimate = None if estimate_usd is None else money(estimate_usd)
        with self._lock:
            if call_id in self._pending or call_id in self._records:
                raise ValueError("call_id já registado.")
            summary = self.summary()
            if self.budget_usd is not None:
                if estimate is None:
                    raise BudgetBlocked("Falta uma reserva de custo para esta chamada.")
                if summary.unknown_calls:
                    raise BudgetBlocked("Existe uma chamada com custo desconhecido.")
                if summary.over_budget or estimate > summary.remaining_usd:
                    raise BudgetBlocked("A chamada ultrapassaria o orçamento disponível.")
            self._pending[call_id] = estimate

    def settle(self, record: UsageRecord) -> None:
        with self._lock:
            if record.call_id not in self._pending:
                raise ValueError("A chamada não tem uma reserva ativa.")
            # Mesmo um custo superior à reserva deve ficar registado.
            del self._pending[record.call_id]
            self._records[record.call_id] = record

    def summary(self) -> CostSummary:
        with self._lock:
            reported = Decimal("0")
            estimated = Decimal("0")
            unknown = 0
            for record in self._records.values():
                if record.actual_cost_usd is not None:
                    reported += record.actual_cost_usd
                elif record.estimated_cost_usd is not None:
                    estimated += record.estimated_cost_usd
                else:
                    unknown += 1
            reserved = sum((value or Decimal("0") for value in self._pending.values()), Decimal("0"))
            unknown += sum(value is None for value in self._pending.values())
            committed = reported + estimated + reserved
            remaining = None if self.budget_usd is None or unknown else max(Decimal("0"), self.budget_usd - committed)
            return CostSummary(
                budget_usd=self.budget_usd, reported_cost_usd=reported,
                estimated_cost_usd=estimated, reserved_usd=reserved,
                unknown_calls=unknown, calls=len(self._records), remaining_usd=remaining,
                over_budget=self.budget_usd is not None and committed > self.budget_usd,
            )
