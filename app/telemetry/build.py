from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from decimal import Decimal
from pathlib import Path
from threading import RLock
from time import perf_counter
from typing import TYPE_CHECKING
import json

if TYPE_CHECKING:
    from app.registry.models import ModelRegistry
    from app.decisions.service import DecisionService

from app.telemetry.costs import BudgetBlocked, CostTracker
from app.registry.mcp import CapabilityBlocked
from app.planning.research_validation import ResearchPlanningBlocked
from app.decisions.service import DecisionBlocked
from app.decisions.schemas import DecisionRecord
from app.retrieval.errors import RetrievalBlocked
from app.telemetry.schemas import BuildEvent, BuildStage, UsageRecord


active_build: ContextVar["BuildTelemetry | None"] = ContextVar("active_build", default=None)


def print_event(event: BuildEvent) -> None:
    costs = event.costs
    limit = "sem limite" if costs.budget_usd is None else f"${costs.budget_usd}"
    print(
        f"[{event.stage.value}] {event.status} | {event.duration_seconds:.2f}s | "
        f"reportado=${costs.reported_cost_usd} | estimado=${costs.estimated_cost_usd} | "
        f"desconhecidos={costs.unknown_calls} | limite={limit}",
        flush=True,
    )


class BuildTelemetry:
    def __init__(
        self, build_id: str, directory: Path, budget_usd: Decimal | None,
        call_reservation_usd: Decimal | None = None,
        sink: Callable[[BuildEvent], None] | None = print_event,
        decision_service: "DecisionService | None" = None,
        model_provider: str | None = None,
        model: str | None = None,
    ):
        self.build_id = build_id
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=False)
        self.tracker = CostTracker(budget_usd)
        self.call_reservation_usd = call_reservation_usd
        self.current_stage = BuildStage.PLANNING
        self.sink = sink
        self._lock = RLock()
        self.model_registry: ModelRegistry | None = None
        self.decision_service = decision_service
        self.model_provider = model_provider
        self.model = model
        self.research_protocol_sha256: str | None = None
        self.retrieval_context: str | None = None
        self.skill_context: str | None = None
        if model_provider and model:
            (self.directory / "model_selection.json").write_text(
                json.dumps({"provider": model_provider, "model": model}, indent=2),
                encoding="utf-8",
            )

    def emit(self, stage: BuildStage, status: str, duration: float = 0, error_type: str | None = None):
        event = BuildEvent(
            build_id=self.build_id, stage=stage, status=status,
            duration_seconds=duration, error_type=error_type, costs=self.tracker.summary(),
        )
        with self._lock:
            with (self.directory / "events.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(event.model_dump_json() + "\n")
        if self.sink is not None:
            self.sink(event)

    def record_usage(self, usage: UsageRecord) -> None:
        with self._lock:
            self.tracker.settle(usage)
            with (self.directory / "usage.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(usage.model_dump_json() + "\n")

    def record_decision(self, decision: DecisionRecord) -> None:
        with self._lock:
            with (self.directory / "decisions.jsonl").open("a", encoding="utf-8") as handle:
                handle.write(decision.model_dump_json() + "\n")

    @contextmanager
    def stage(self, stage: BuildStage) -> Iterator[None]:
        self.current_stage = stage
        started = perf_counter()
        self.emit(stage, "started")
        try:
            yield
        except BaseException as error:
            self.emit(stage, "blocked" if isinstance(error, (BudgetBlocked, CapabilityBlocked, ResearchPlanningBlocked, DecisionBlocked, RetrievalBlocked)) else "failed",
                      perf_counter() - started, type(error).__name__)
            raise
        else:
            self.emit(stage, "passed", perf_counter() - started)

    @contextmanager
    def activate(self) -> Iterator[None]:
        token = active_build.set(self)
        try:
            yield
        finally:
            active_build.reset(token)

    def finish(self, status: str) -> None:
        self.emit(BuildStage.FINISHED, status)
        (self.directory / "cost_summary.json").write_text(
            self.tracker.summary().model_dump_json(indent=2), encoding="utf-8",
        )
