from datetime import datetime, timezone
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class BuildStage(StrEnum):
    RETRIEVAL = "retrieval"
    RETRIEVAL_EVALUATION = "retrieval_evaluation"
    RESEARCH_QUESTION = "research_question"
    RESEARCH_PROTOCOL = "research_protocol"
    SCIENTIFIC_ARCHITECT = "scientific_architect"
    PLANNING = "planning"
    CAPABILITIES = "capabilities"
    PREPARING = "preparing"
    GENERATING = "generating"
    REPAIRING = "repairing"
    FALLBACK_SCAFFOLD = "fallback_scaffold"
    ACCEPTANCE = "acceptance"
    GATES = "gates"
    TESTS = "tests"
    FINISHED = "finished"


class TelemetryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)


class UsageRecord(TelemetryRecord):
    call_id: str
    stage: BuildStage
    provider: str
    model: str
    kind: Literal["model", "tool", "decision"] = "model"
    status: Literal["succeeded", "failed"]
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    duration_seconds: float = Field(ge=0)
    reservation_usd: Decimal | None = Field(default=None, ge=0)
    estimated_cost_usd: Decimal | None = Field(default=None, ge=0)
    actual_cost_usd: Decimal | None = Field(default=None, ge=0)
    resolved_model: str | None = None
    pricing_source: str | None = None


class CostSummary(TelemetryRecord):
    budget_usd: Decimal | None
    reported_cost_usd: Decimal
    estimated_cost_usd: Decimal
    reserved_usd: Decimal
    unknown_calls: int
    calls: int
    remaining_usd: Decimal | None
    over_budget: bool


class BuildEvent(TelemetryRecord):
    build_id: str
    stage: BuildStage
    status: Literal["started", "passed", "failed", "skipped", "blocked"]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    duration_seconds: float = Field(default=0, ge=0)
    error_type: str | None = None
    costs: CostSummary
