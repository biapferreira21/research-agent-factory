from decimal import Decimal

import pytest

from app.telemetry.costs import BudgetBlocked, CostTracker
from app.telemetry.schemas import BuildStage, UsageRecord


def record(call_id="one", actual=None, estimated=None):
    return UsageRecord(
        call_id=call_id, stage=BuildStage.PLANNING, provider="fake", model="fake",
        status="succeeded", duration_seconds=0,
        actual_cost_usd=actual, estimated_cost_usd=estimated,
    )


def test_reservation_prevents_overspending_with_inflight_calls():
    tracker = CostTracker(Decimal("1"))
    tracker.reserve("one", Decimal("0.60"))
    with pytest.raises(BudgetBlocked):
        tracker.reserve("two", Decimal("0.41"))
    tracker.reserve("two", Decimal("0.40"))
    assert tracker.summary().remaining_usd == 0


def test_actual_cost_releases_unused_reservation_exactly():
    tracker = CostTracker(Decimal("1"))
    tracker.reserve("one", Decimal("0.8"))
    tracker.settle(record(actual="0.1"))
    tracker.reserve("two", Decimal("0.9"))
    assert tracker.summary().reported_cost_usd == Decimal("0.1")
    assert tracker.summary().remaining_usd == 0


def test_unknown_cost_is_not_zero_and_blocks_next_call():
    tracker = CostTracker(Decimal("1"))
    tracker.reserve("one", Decimal("0.2"))
    tracker.settle(record())
    assert tracker.summary().unknown_calls == 1
    assert tracker.summary().remaining_usd is None
    with pytest.raises(BudgetBlocked, match="desconhecido"):
        tracker.reserve("two", Decimal("0.2"))


def test_reported_zero_is_known_and_estimates_stay_separate():
    tracker = CostTracker(Decimal("1"))
    tracker.reserve("one", Decimal("0.2"))
    tracker.settle(record(actual="0"))
    tracker.reserve("two", Decimal("0.2"))
    tracker.settle(record("two", estimated="0.15"))
    summary = tracker.summary()
    assert summary.unknown_calls == 0
    assert summary.reported_cost_usd == 0
    assert summary.estimated_cost_usd == Decimal("0.15")
    assert summary.remaining_usd == Decimal("0.85")


def test_unexpected_overrun_is_recorded_not_discarded():
    tracker = CostTracker(Decimal("1"))
    tracker.reserve("one", Decimal("0.2"))
    tracker.settle(record(actual="1.20"))
    assert tracker.summary().over_budget
    assert tracker.summary().reported_cost_usd == Decimal("1.20")
    with pytest.raises(BudgetBlocked):
        tracker.reserve("two", Decimal("0"))


def test_unpriced_call_is_rejected_before_reserving():
    tracker = CostTracker(Decimal("1"))
    with pytest.raises(BudgetBlocked):
        tracker.reserve("one", None)
    assert tracker.summary().calls == 0
    assert tracker.summary().unknown_calls == 0


def test_duplicate_settlement_and_ids_are_rejected():
    tracker = CostTracker()
    tracker.reserve("one", None)
    with pytest.raises(ValueError):
        tracker.reserve("one", None)
    tracker.settle(record(actual="0.1"))
    with pytest.raises(ValueError):
        tracker.settle(record(actual="0.1"))
    with pytest.raises(ValueError):
        tracker.reserve("one", None)
    assert tracker.summary().reported_cost_usd == Decimal("0.1")


@pytest.mark.parametrize("value", ["-1", "NaN", "Infinity"])
def test_invalid_money_is_rejected(value):
    with pytest.raises(ValueError):
        CostTracker(Decimal(value))
    with pytest.raises(ValueError):
        CostTracker().reserve("one", Decimal(value))
