from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DecisionContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class ModelChoice(DecisionContract):
    id: str = Field(min_length=1)
    provider: str
    model: str
    reservation_usd: Decimal = Field(ge=0)
    context_window: int = Field(gt=0)
    tool_calling: bool
    structured_output: bool


class OptionChoice(DecisionContract):
    id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=1500)


class DecisionState(DecisionContract):
    stage: str
    preferred_choice_id: str
    remaining_budget_usd: Decimal | None = Field(default=None, ge=0)
    research_protocol_sha256: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    task: str | None = Field(default=None, max_length=5000)


class DecisionRequest(DecisionContract):
    request_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    purpose: Literal["model_routing", "skill_selection", "rag_strategy", "eval_dimension", "capability_selection"] = "model_routing"
    state: DecisionState
    candidates: tuple[ModelChoice | OptionChoice, ...]

    @model_validator(mode="after")
    def unique_candidates(self):
        ids = [candidate.id for candidate in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("IDs de candidatos duplicados.")
        return self


class ChoiceProbability(DecisionContract):
    choice_id: str
    probability: float = Field(ge=0, le=1, strict=True)


class DecisionResponse(DecisionContract):
    request_id: str
    choice_id: str
    confidence: float = Field(ge=0, le=1, strict=True)
    probabilities: tuple[ChoiceProbability, ...] | None = None


class DecisionPolicy(DecisionContract):
    min_confidence: float = Field(default=0.80, ge=0, le=1, strict=True)
    on_low_confidence: Literal["block", "fallback"] = "block"


class DecisionRecord(DecisionContract):
    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str
    state: DecisionState
    policy: DecisionPolicy
    candidate_ids: tuple[str, ...]
    backend: str
    attempt: Literal["primary", "fallback"]
    status: Literal["accepted", "rejected", "low_confidence"]
    reason: str | None = None
    response: DecisionResponse | None = None


class DecisionResult(DecisionContract):
    choice_id: str
    confidence: float
    backend: str
    used_fallback: bool
