import json
from decimal import Decimal

import httpx
import pytest

from app.decisions.jev import JevBackend
from app.decisions.schemas import DecisionRequest, DecisionState, ModelChoice
from app.decisions.service import DecisionBlocked, DecisionService
from app.telemetry.build import BuildTelemetry


@pytest.fixture
def request_data():
    return DecisionRequest(state=DecisionState(stage="planning", preferred_choice_id="a"),
                           candidates=(ModelChoice(id="a", provider="openrouter", model="free",
                           reservation_usd=0, context_window=1000, tool_calling=True,
                           structured_output=True),))


def response_data():
    return {"answers": {"route": {"type": "choice", "choice": "a", "confidence": 1.0,
                                 "probabilities": {"a": 1.0}}},
            "usage": {"cost": 0.000014994}}


def run(tmp_path, request_data, handler, budget="1"):
    telemetry = BuildTelemetry("test", tmp_path / "run", Decimal(budget), sink=None)
    backend = JevBackend("SECRET", transport=httpx.MockTransport(handler))
    with telemetry.activate():
        result = DecisionService(backend).decide(request_data, sink=telemetry.record_decision)
    return result, telemetry


def test_http_contract_and_shared_cost(tmp_path, request_data):
    def handler(request):
        assert str(request.url) == JevBackend.endpoint
        assert request.headers["authorization"] == "Bearer SECRET"
        payload = json.loads(request.content)
        assert payload["model"] == JevBackend.model
        assert set(payload["questions"]["route"]["criteria"]) == {"a"}
        assert request.extensions["timeout"]["read"] == 30
        return httpx.Response(200, json=response_data())
    result, telemetry = run(tmp_path, request_data, handler)
    assert result.choice_id == "a"
    assert telemetry.tracker.summary().reported_cost_usd == Decimal("0.000014994")
    assert telemetry.tracker.summary().reserved_usd == 0
    usage = json.loads((telemetry.directory / "usage.jsonl").read_text())
    assert usage["kind"] == "decision"
    assert "SECRET" not in (telemetry.directory / "usage.jsonl").read_text()


@pytest.mark.parametrize("mode", ["timeout", "http", "redirect", "json", "missing_cost", "nan", "negative",
                                 "unknown_choice", "missing_probabilities", "wrong_type", "low_confidence"])
def test_failures_block_and_settle_once(tmp_path, request_data, mode):
    calls = []
    def handler(request):
        calls.append(request)
        if mode == "timeout":
            raise httpx.ReadTimeout("SECRET")
        if mode == "http":
            return httpx.Response(500, text="SECRET")
        if mode == "redirect":
            return httpx.Response(307, headers={"location": "https://example.com"})
        if mode == "json":
            return httpx.Response(200, text="SECRET")
        data = response_data()
        if mode == "missing_cost":
            data.pop("usage")
        elif mode == "nan":
            data["usage"]["cost"] = "NaN"
        elif mode == "negative":
            data["usage"]["cost"] = -1
        elif mode == "unknown_choice":
            data["answers"]["route"]["choice"] = "invented"
        elif mode == "missing_probabilities":
            data["answers"]["route"].pop("probabilities")
        elif mode == "wrong_type":
            data["answers"]["route"]["type"] = "score"
        elif mode == "low_confidence":
            data["answers"]["route"]["confidence"] = 0.1
        return httpx.Response(200, json=data)
    with pytest.raises(DecisionBlocked):
        run(tmp_path, request_data, handler)
    assert len(calls) == 1
    usage = json.loads((tmp_path / "run" / "usage.jsonl").read_text())
    assert usage["actual_cost_usd"] == ("0.000014994" if mode in {
        "unknown_choice", "missing_probabilities", "wrong_type", "low_confidence"} else None)
    assert "SECRET" not in (tmp_path / "run" / "decisions.jsonl").read_text()


def test_insufficient_budget_prevents_http(tmp_path, request_data):
    with pytest.raises(DecisionBlocked):
        run(tmp_path, request_data, lambda _: pytest.fail("HTTP must not run"), budget="0.001")
    assert not (tmp_path / "run" / "usage.jsonl").exists()


def test_no_build_prevents_http(request_data):
    with pytest.raises(DecisionBlocked, match="ativo"):
        JevBackend("SECRET").decide(request_data)


def test_unknown_cost_blocks_next_call(tmp_path, request_data):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})
    telemetry = BuildTelemetry("test", tmp_path / "run", Decimal(1), sink=None)
    service = DecisionService(JevBackend("SECRET", transport=httpx.MockTransport(handler)))
    with telemetry.activate():
        for _ in range(2):
            with pytest.raises(DecisionBlocked):
                service.decide(request_data)
    assert len(calls) == 1
    assert telemetry.tracker.summary().unknown_calls == 1


def test_overrun_is_recorded_and_blocks(tmp_path, request_data):
    data = response_data()
    data["usage"]["cost"] = 2
    with pytest.raises(DecisionBlocked):
        run(tmp_path, request_data, lambda _: httpx.Response(200, json=data))
    assert json.loads((tmp_path / "run" / "usage.jsonl").read_text())["actual_cost_usd"] == "2"
