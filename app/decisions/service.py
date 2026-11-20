from collections.abc import Callable
from math import isclose
from typing import Protocol

from pydantic import ValidationError

from app.decisions.schemas import (
    DecisionPolicy, DecisionRecord, DecisionRequest, DecisionResponse, DecisionResult,
)


class DecisionBlocked(RuntimeError):
    pass


class DecisionBackend(Protocol):
    name: str

    def decide(self, request: DecisionRequest) -> DecisionResponse: ...


def validate_response(request: DecisionRequest, response: DecisionResponse) -> None:
    ids = {candidate.id for candidate in request.candidates}
    if response.request_id != request.request_id:
        raise ValueError("wrong_request")
    if response.choice_id not in ids:
        raise ValueError("unknown_choice")
    if response.probabilities is not None:
        probability_ids = [item.choice_id for item in response.probabilities]
        if len(probability_ids) != len(ids) or set(probability_ids) != ids:
            raise ValueError("invalid_probability_candidates")
        if not isclose(sum(item.probability for item in response.probabilities), 1.0, abs_tol=1e-6, rel_tol=0):
            raise ValueError("invalid_probability_total")


class DecisionService:
    def __init__(self, primary: DecisionBackend, *, policy: DecisionPolicy | None = None,
                 fallback: DecisionBackend | None = None):
        self.primary = primary
        self.policy = policy if policy is not None else DecisionPolicy()
        self.fallback = fallback

    def decide(self, request: DecisionRequest, *, sink: Callable[[DecisionRecord], None] | None = None) -> DecisionResult:
        # Revalidar mesmo instâncias construídas/alteradas sem validação pelo chamador.
        request = DecisionRequest.model_validate(request.model_dump())
        candidates = tuple(item.id for item in request.candidates)

        def emit(backend, attempt, status, reason=None, response=None):
            if sink is not None:
                sink(DecisionRecord(request_id=request.request_id, stage=request.state.stage,
                                    state=request.state, policy=self.policy,
                                    candidate_ids=candidates, backend=backend.name, attempt=attempt,
                                    status=status, reason=reason, response=response))

        if not candidates:
            emit(self.primary, "primary", "rejected", "no_candidates")
            raise DecisionBlocked("Não há candidatos elegíveis para a decisão.")

        backends = [("primary", self.primary)]
        if self.policy.on_low_confidence == "fallback" and self.fallback is not None:
            backends.append(("fallback", self.fallback))
        for attempt, backend in backends:
            try:
                raw = backend.decide(request)
            except Exception as error:
                # Não guardar a mensagem: pode incluir dados do pedido ou credenciais.
                emit(backend, attempt, "rejected", "backend_error")
                raise DecisionBlocked("O decisor falhou; a decisão foi bloqueada.") from error
            try:
                response = DecisionResponse.model_validate(raw.model_dump())
                validate_response(request, response)
            except (ValidationError, ValueError, AttributeError, TypeError) as error:
                emit(backend, attempt, "rejected", "invalid_response")
                raise DecisionBlocked("O decisor devolveu uma escolha ou resposta inválida.") from error
            if response.confidence < self.policy.min_confidence:
                emit(backend, attempt, "low_confidence", "below_threshold", response)
                continue
            emit(backend, attempt, "accepted", response=response)
            return DecisionResult(choice_id=response.choice_id, confidence=response.confidence,
                                  backend=backend.name, used_fallback=attempt == "fallback")
        raise DecisionBlocked("Confiança insuficiente; não foi aceite nenhuma decisão.")
