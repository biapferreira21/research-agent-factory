import json
from datetime import date, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

import app.models as models
import app.registry.runtime as runtime
from app.registry.models import ModelPricing, ModelRegistry, RegisteredModel
from app.telemetry.build import BuildTelemetry
from app.telemetry.callbacks import UsageCallback
from app.telemetry.costs import BudgetBlocked


@pytest.fixture
def entry():
    return RegisteredModel(
        provider="openrouter", model="test/model", enabled=True, tool_calling=True,
        context_window=10000, max_output_tokens=1000,
        pricing=ModelPricing(input_usd_per_million="2", output_usd_per_million="8",
                             source="test-only", checked_on=date.today()),
    )


def callback_for(tmp_path, entry, manual=None):
    telemetry = BuildTelemetry("id", tmp_path / "logs", Decimal("1"), manual, sink=None)
    return telemetry, UsageCallback(telemetry, entry.provider, entry.model, entry)


def make_response(cost=None, tokens=True):
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(
        content="hello", response_metadata={} if cost is None else {"cost": cost},
        usage_metadata={"input_tokens": 1000, "output_tokens": 500, "total_tokens": 1500} if tokens else None,
    ))]], llm_output={"model_name": "actual/resolved-model"})


def configure(monkeypatch, tmp_path, entry):
    path = tmp_path / "registry.json"
    path.write_text(ModelRegistry(models=(entry,)).model_dump_json(), encoding="utf-8")
    settings = SimpleNamespace(
        model_provider=entry.provider, openrouter_model=entry.model, openai_model=entry.model,
        openrouter_api_key="dummy", openai_api_key="dummy", allow_model_router=False,
    )
    monkeypatch.setattr(models, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime, "get_settings", lambda: settings)
    monkeypatch.setattr(runtime, "get_model_registry_path", lambda: path)
    return path


def test_automatic_reservation_and_usage_estimate(tmp_path, entry):
    telemetry, callback = callback_for(tmp_path, entry)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    assert telemetry.tracker.summary().reserved_usd == Decimal("0.028")
    callback.on_llm_end(make_response(), run_id=run_id)
    assert telemetry.tracker.summary().estimated_cost_usd == Decimal("0.006")
    assert telemetry.tracker.summary().unknown_calls == 0
    callback.on_chat_model_start({}, [], run_id=uuid4())
    usage = json.loads((telemetry.directory / "usage.jsonl").read_text())
    assert usage["resolved_model"] == "actual/resolved-model"
    assert usage["pricing_source"] == "test-only"


@pytest.mark.parametrize("manual,expected", [(Decimal("0.001"), Decimal("0.028")), (Decimal("0.10"), Decimal("0.10"))])
def test_manual_reservation_cannot_reduce_automatic_reservation(tmp_path, entry, manual, expected):
    telemetry, callback = callback_for(tmp_path, entry, manual)
    callback.on_chat_model_start({}, [], run_id=uuid4())
    assert telemetry.tracker.summary().reserved_usd == expected


def test_reported_cost_takes_precedence_over_token_estimate(tmp_path, entry):
    telemetry, callback = callback_for(tmp_path, entry)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_end(make_response(cost="0.004"), run_id=run_id)
    assert telemetry.tracker.summary().reported_cost_usd == Decimal("0.004")
    assert telemetry.tracker.summary().estimated_cost_usd == 0


def test_missing_tokens_and_cost_remain_unknown_even_with_catalog(tmp_path, entry):
    telemetry, callback = callback_for(tmp_path, entry)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_end(make_response(tokens=False), run_id=run_id)
    assert telemetry.tracker.summary().unknown_calls == 1


@pytest.mark.parametrize("params", [
    {"max_tokens": 1001}, {"max_completion_tokens": 1001}, {"n": 2},
    {"max_tokens": None}, {"max_tokens": 0},
    {"max_tokens": 2000, "max_completion_tokens": 100},
])
def test_output_overrides_cannot_bypass_reservation(tmp_path, entry, params):
    telemetry, callback = callback_for(tmp_path, entry)
    with pytest.raises(BudgetBlocked):
        callback.on_chat_model_start({}, [], run_id=uuid4(), invocation_params=params)
    assert telemetry.tracker.summary().reserved_usd == 0


def test_unpriced_multimodal_input_is_rejected(tmp_path, entry):
    _, callback = callback_for(tmp_path, entry)
    with pytest.raises(BudgetBlocked):
        callback.on_chat_model_start({}, [[HumanMessage(content=[
            {"type": "image_url", "image_url": {"url": "https://example.com/image.png"}}
        ])]], run_id=uuid4())


def test_expired_price_is_rechecked_at_call_time(tmp_path, entry):
    data = entry.model_dump()
    data["pricing"]["checked_on"] = date.today() - timedelta(days=30)
    _, callback = callback_for(tmp_path, RegisteredModel.model_validate(data))
    with pytest.raises(BudgetBlocked, match="expiraram"):
        callback.on_chat_model_start({}, [], run_id=uuid4())


def test_catalog_snapshot_is_stable_within_build(monkeypatch, tmp_path, entry):
    path = configure(monkeypatch, tmp_path, entry)
    telemetry, _ = callback_for(tmp_path, entry)
    with telemetry.activate():
        original = runtime.get_registry()
        path.write_text('{"models": []}', encoding="utf-8")
        assert runtime.get_registry() == original
    assert (telemetry.directory / "model_registry.json").is_file()
    assert runtime.get_registry().models == ()


@pytest.mark.parametrize("provider", ["openai", "openrouter"])
def test_client_receives_output_limit_and_callback(monkeypatch, tmp_path, entry, provider):
    entry = RegisteredModel.model_validate(dict(entry.model_dump(), provider=provider))
    configure(monkeypatch, tmp_path, entry)
    captured = {}

    def fake_client(**kwargs):
        captured.update(kwargs)
        return FakeMessagesListChatModel(
            responses=[make_response().generations[0][0].message], callbacks=kwargs["callbacks"],
        )

    monkeypatch.setattr(models, "ChatOpenAI", fake_client)
    monkeypatch.setattr(models, "ChatOpenRouter", fake_client)
    telemetry, _ = callback_for(tmp_path, entry)
    with telemetry.activate():
        client = models.get_model()
        client.invoke("hello")
        client.invoke("hello again")
    assert captured["max_tokens"] == 1000
    assert captured["max_retries"] == 0
    assert captured["timeout"] == (150 if provider == "openai" else 150000)
    assert telemetry.tracker.summary().calls == 2
    assert telemetry.tracker.summary().estimated_cost_usd == Decimal("0.012")


def test_interactive_model_timeout_overrides_build_default(monkeypatch, tmp_path, entry):
    configure(monkeypatch, tmp_path, entry)
    captured = {}
    monkeypatch.setattr(models, "ChatOpenRouter", lambda **kwargs: captured.update(kwargs) or object())
    models.get_model(timeout_seconds=45)
    assert captured["timeout"] == 45000


def test_unapproved_model_is_blocked_before_client_creation(monkeypatch, tmp_path, entry):
    disabled = RegisteredModel.model_validate(dict(entry.model_dump(), enabled=False))
    configure(monkeypatch, tmp_path, disabled)
    monkeypatch.setattr(models, "ChatOpenRouter", lambda **_: pytest.fail("Client constructed"))
    with pytest.raises(BudgetBlocked):
        models.get_model()


def test_required_native_structured_output_is_enforced(monkeypatch, tmp_path, entry):
    configure(monkeypatch, tmp_path, entry)
    with pytest.raises(BudgetBlocked):
        models.get_model(structured_output=True)
