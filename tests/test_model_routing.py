import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest

import app.decisions.model_router as routing
import app.models as models
from app.builder.harness import BuilderHarness
from app.decisions.backends import ConfiguredModelBackend, FixedDecisionBackend
from app.decisions.schemas import DecisionResponse
from app.decisions.service import DecisionBlocked, DecisionService
from app.registry.models import ModelPricing, ModelRegistry, RegisteredModel
from app.telemetry.build import BuildTelemetry
from app.telemetry.costs import BudgetBlocked
from app.telemetry.schemas import BuildStage, UsageRecord
from harness_offline_demo import offline_planner


def entry(name="configured", **changes):
    data = dict(provider="openrouter", model=name, enabled=True, context_window=1000, max_output_tokens=100,
                tool_calling=True, structured_output=True,
                pricing=ModelPricing(input_usd_per_million="1", output_usd_per_million="1",
                                     source="test-only", checked_on=date.today()))
    data.update(changes)
    return RegisteredModel(**data)


def setup_routing(monkeypatch, tmp_path, entries=None, service=None):
    registry = ModelRegistry(models=tuple(entries if entries is not None else [entry(), entry("other")]))
    monkeypatch.setattr(routing, "get_registry", lambda: registry)
    monkeypatch.setattr(routing, "get_settings", lambda: SimpleNamespace(allow_model_router=False))
    return BuildTelemetry("test", tmp_path / "logs", Decimal("1"), sink=None, decision_service=service)


def route():
    return routing.route_model("openrouter", "configured", tool_calling=True, structured_output=True)


def test_default_preserves_configured_model_and_audits_decision(monkeypatch, tmp_path):
    telemetry = setup_routing(monkeypatch, tmp_path)
    with telemetry.activate():
        assert route().model == "configured"
    record = json.loads((telemetry.directory / "decisions.jsonl").read_text())
    assert record["backend"] == "configured_model_rule"
    assert record["status"] == "accepted"
    assert record["state"]["remaining_budget_usd"] == "1"
    assert record["policy"]["min_confidence"] == .8


def test_filters_before_calling_backend(monkeypatch, tmp_path):
    expired = ModelPricing(input_usd_per_million="0", output_usd_per_million="0",
                           source="test", checked_on=date.today() - timedelta(days=30))
    expensive = ModelPricing(input_usd_per_million="2000", output_usd_per_million="2000",
                             source="test", checked_on=date.today())
    entries = [entry(), entry("disabled", enabled=False), entry("no-tools", tool_calling=False),
               entry("no-structured", structured_output=False), entry("router", is_router=True),
               entry("old", pricing=expired), entry("expensive", pricing=expensive), entry("other-provider", provider="openai")]
    seen = []
    class Spy:
        name = "spy"
        def decide(self, request):
            seen.append(request)
            return ConfiguredModelBackend().decide(request)
    telemetry = setup_routing(monkeypatch, tmp_path, entries, DecisionService(Spy()))
    telemetry.research_protocol_sha256 = "a" * 64
    with telemetry.activate():
        route()
    assert [choice.id for choice in seen[0].candidates] == ["openrouter:configured"]
    assert seen[0].state.research_protocol_sha256 == "a" * 64


def test_disallowed_choice_cannot_escape_filtered_candidates(monkeypatch, tmp_path):
    telemetry = setup_routing(monkeypatch, tmp_path,
                             service=DecisionService(FixedDecisionBackend("openrouter:invented")))
    with telemetry.activate(), pytest.raises(DecisionBlocked):
        route()


def test_manual_reservation_is_included_in_filter(monkeypatch, tmp_path):
    telemetry = setup_routing(monkeypatch, tmp_path)
    telemetry.call_reservation_usd = Decimal("2")
    with telemetry.activate(), pytest.raises(DecisionBlocked, match="candidatos"):
        route()


def test_unknown_cost_blocks_routing(monkeypatch, tmp_path):
    telemetry = setup_routing(monkeypatch, tmp_path)
    telemetry.tracker.reserve("unknown", Decimal("0.1"))
    telemetry.tracker.settle(UsageRecord(call_id="unknown", stage=BuildStage.PLANNING,
                                        provider="fake", model="fake", status="failed", duration_seconds=0))
    with telemetry.activate(), pytest.raises(BudgetBlocked, match="desconhecido"):
        route()


def test_budget_is_rechecked_after_decision(monkeypatch, tmp_path):
    class Spender:
        name = "spender"
        def decide(self, request):
            telemetry.tracker.reserve("other-call", Decimal("1"))
            return ConfiguredModelBackend().decide(request)
    telemetry = setup_routing(monkeypatch, tmp_path, service=DecisionService(Spender()))
    with telemetry.activate(), pytest.raises(DecisionBlocked, match="deixou"):
        route()


def test_client_uses_selected_model_not_configured_name(monkeypatch, tmp_path):
    telemetry = setup_routing(monkeypatch, tmp_path, service=DecisionService(FixedDecisionBackend("openrouter:other")))
    monkeypatch.setattr(models, "get_settings", lambda: SimpleNamespace(
        model_provider="openrouter", openrouter_model="configured", openrouter_api_key="dummy",
    ))
    captured = {}
    def fake_client(**kwargs):
        captured.update(kwargs)
        return object()
    monkeypatch.setattr(models, "ChatOpenRouter", fake_client)
    with telemetry.activate():
        models.get_model()
    assert captured["model"] == "other"
    assert captured["callbacks"][0].model == "other"
    assert captured["max_tokens"] == 100


def test_harness_returns_blocked_on_low_confidence(monkeypatch, tmp_path):
    registry = ModelRegistry(models=(entry(),))
    monkeypatch.setattr(routing, "get_registry", lambda: registry)
    monkeypatch.setattr(routing, "get_settings", lambda: SimpleNamespace(allow_model_router=False))
    def planner(requirement):
        route()
        return offline_planner(requirement)
    result = BuilderHarness(root=tmp_path, planner=planner, event_sink=None,
                            decision_service=DecisionService(FixedDecisionBackend("openrouter:configured", .2))).build("demo")
    assert result.status == "blocked"
    assert result.workspace == ""
    assert result.costs.calls == 0
