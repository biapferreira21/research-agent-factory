"""Traduz callbacks LangChain para registos locais, sem guardar prompts."""

from decimal import Decimal, InvalidOperation
from time import perf_counter

from langchain_core.callbacks import BaseCallbackHandler

from app.telemetry.build import BuildTelemetry
from app.telemetry.costs import BudgetBlocked
from app.telemetry.schemas import UsageRecord
from app.registry.models import RegisteredModel


def valid_cost(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        cost = Decimal(str(value))
    except InvalidOperation:
        return None
    return cost if cost.is_finite() and cost >= 0 else None


class UsageCallback(BaseCallbackHandler):
    # Uma recusa do orçamento tem de interromper a chamada antes do provider.
    raise_error = True
    run_inline = True

    def __init__(self, telemetry: BuildTelemetry, provider: str, model: str, entry: RegisteredModel | None = None):
        self.telemetry = telemetry
        self.provider = provider
        self.model = model
        self.entry = entry
        self._started = {}

    def on_chat_model_start(self, serialized, messages, *, run_id, **kwargs):
        call_id = str(run_id)
        reservation = self.telemetry.call_reservation_usd
        if self.entry is not None:
            if not self.entry.pricing.is_current():
                raise BudgetBlocked("Os preços do modelo expiraram; atualiza o catálogo.")
            params = kwargs.get("invocation_params") or {}
            for key in ("max_completion_tokens", "max_tokens"):
                if key in params:
                    requested_output = params[key]
                    if type(requested_output) is not int or not 0 < requested_output <= self.entry.max_output_tokens:
                        raise BudgetBlocked("O output pedido tem de respeitar o limite aprovado.")
            if params.get("n", 1) != 1:
                raise BudgetBlocked("O orçamento suporta uma resposta por chamada.")
            for batch in messages:
                for message in batch:
                    content = message.content
                    if not isinstance(content, str) and any(
                        not isinstance(block, str) and (not isinstance(block, dict) or block.get("type") != "text")
                        for block in content
                    ):
                        raise BudgetBlocked("Este catálogo só estima mensagens de texto.")
            automatic = self.entry.reservation()
            # Uma reserva manual maior continua útil; uma menor não contorna o cálculo.
            reservation = max(automatic, reservation or Decimal("0"))
        self.telemetry.tracker.reserve(call_id, reservation)
        self._started[call_id] = (perf_counter(), self.telemetry.current_stage, reservation)

    def on_llm_end(self, response, *, run_id, **kwargs):
        usage = {}
        metadata = {}
        if response.generations and response.generations[0]:
            message = getattr(response.generations[0][0], "message", None)
            usage = getattr(message, "usage_metadata", None) or {}
            metadata = getattr(message, "response_metadata", None) or {}
        metadata = dict(metadata)
        metadata.setdefault("model_name", (response.llm_output or {}).get("model_name"))
        self._complete(str(run_id), "succeeded", usage, metadata)

    def on_llm_error(self, error, *, run_id, **kwargs):
        # Uma falha de rede não prova que a chamada foi gratuita.
        self._complete(str(run_id), "failed", {}, {})

    def _complete(self, call_id, status, usage, metadata):
        if call_id not in self._started:
            return
        started, stage, reservation = self._started.pop(call_id)
        actual = valid_cost(metadata.get("cost"))
        estimated = None
        input_tokens, output_tokens = usage.get("input_tokens"), usage.get("output_tokens")
        if actual is None and self.entry is not None:
            pricing = self.entry.pricing
            if pricing.request_usd == pricing.input_usd_per_million == pricing.output_usd_per_million == 0:
                # A failed call through a catalogue entry that is unconditionally free still costs zero.
                estimated = Decimal("0")
            elif status == "succeeded" and all(type(value) is int and value >= 0
                                                for value in (input_tokens, output_tokens)):
                estimated = pricing.estimate(input_tokens, output_tokens)
        self.telemetry.record_usage(UsageRecord(
            call_id=call_id, stage=stage, provider=self.provider, model=self.model,
            status=status, input_tokens=usage.get("input_tokens"),
            output_tokens=usage.get("output_tokens"), duration_seconds=perf_counter() - started,
            reservation_usd=reservation,
            actual_cost_usd=actual, estimated_cost_usd=estimated,
            resolved_model=metadata.get("model_name"),
            pricing_source=self.entry.pricing.source if self.entry else None,
        ))
        if self.telemetry.tracker.summary().over_budget:
            raise BudgetBlocked("O custo reportado excedeu o orçamento; novas chamadas estão bloqueadas.")
