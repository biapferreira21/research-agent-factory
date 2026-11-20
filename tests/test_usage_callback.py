import json
from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from app.telemetry.build import BuildTelemetry
from app.telemetry.callbacks import UsageCallback
from app.telemetry.costs import BudgetBlocked
from app.registry.models import ModelPricing, RegisteredModel


def setup_callback(tmp_path, reservation=Decimal("0.2")):
    telemetry = BuildTelemetry("build", tmp_path / "logs", Decimal("1"), reservation, sink=None)
    return telemetry, UsageCallback(telemetry, "fake", "fake-model")


def response(cost=None):
    metadata = {} if cost is None else {"cost": cost}
    return LLMResult(generations=[[ChatGeneration(message=AIMessage(
        content="SECRET_ANSWER", response_metadata=metadata,
        usage_metadata={"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    ))]])


def test_callback_collects_tokens_cost_and_duration(tmp_path):
    telemetry, callback = setup_callback(tmp_path)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_end(response(0.012), run_id=run_id)
    summary = telemetry.tracker.summary()
    assert summary.reported_cost_usd == Decimal("0.012")
    data = json.loads((telemetry.directory / "usage.jsonl").read_text())
    assert data["input_tokens"] == 10
    assert data["output_tokens"] == 5
    assert data["duration_seconds"] >= 0
    assert data["reservation_usd"] == "0.2"
    assert "SECRET" not in str(data)


def test_callback_missing_metadata_blocks_next_call(tmp_path):
    telemetry, callback = setup_callback(tmp_path)
    first = uuid4()
    callback.on_chat_model_start({}, [], run_id=first)
    callback.on_llm_end(response(), run_id=first)
    with pytest.raises(BudgetBlocked):
        callback.on_chat_model_start({}, [], run_id=uuid4())
    assert telemetry.tracker.summary().unknown_calls == 1


def test_failed_call_is_unknown_and_duplicate_end_not_counted(tmp_path):
    telemetry, callback = setup_callback(tmp_path)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_error(RuntimeError("SECRET"), run_id=run_id)
    callback.on_llm_error(RuntimeError("SECRET"), run_id=run_id)
    assert telemetry.tracker.summary().calls == 1
    assert telemetry.tracker.summary().unknown_calls == 1


def test_failed_call_for_unconditionally_free_catalogue_entry_costs_zero(tmp_path):
    telemetry = BuildTelemetry("build", tmp_path / "logs", Decimal("1"), Decimal("0"), sink=None)
    entry = RegisteredModel(
        provider="openrouter", model="openrouter/free", enabled=True, is_router=True,
        context_window=1000, max_output_tokens=100, structured_output=True,
        pricing=ModelPricing(input_usd_per_million=0, output_usd_per_million=0,
                             request_usd=0, source="catalogue", checked_on=date.today()),
    )
    callback = UsageCallback(telemetry, "openrouter", "openrouter/free", entry)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    callback.on_llm_error(RuntimeError("malformed response"), run_id=run_id)
    summary = telemetry.tracker.summary()
    assert summary.unknown_calls == 0
    assert summary.estimated_cost_usd == 0


def test_real_langchain_callback_blocks_before_model_execution(tmp_path):
    telemetry, callback = setup_callback(tmp_path, reservation=None)
    model = FakeListChatModel(responses=["one", "two"], callbacks=[callback])
    with pytest.raises(BudgetBlocked):
        model.invoke("hello")
    assert model.i == 0
    assert telemetry.tracker.summary().calls == 0


def test_real_langchain_callback_records_a_completed_call(tmp_path):
    telemetry, callback = setup_callback(tmp_path)
    model = FakeListChatModel(responses=["one", "two"], callbacks=[callback])
    model.invoke("hello")
    assert model.i == 1
    assert telemetry.tracker.summary().calls == 1
    with pytest.raises(BudgetBlocked):
        model.invoke("hello again")
    assert model.i == 1


def test_overrun_records_cost_then_interrupts(tmp_path):
    telemetry, callback = setup_callback(tmp_path)
    run_id = uuid4()
    callback.on_chat_model_start({}, [], run_id=run_id)
    with pytest.raises(BudgetBlocked):
        callback.on_llm_end(response("1.10"), run_id=run_id)
    assert telemetry.tracker.summary().reported_cost_usd == Decimal("1.10")
