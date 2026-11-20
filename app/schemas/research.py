"""Contratos científicos: descrevem a investigação antes de gerar um agente."""

from typing import Literal
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ResearchContract(BaseModel):
    # Rejeitar campos desconhecidos ajuda a detetar erros de escrita.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ResearchQuestionSpec(ResearchContract):
    question: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    inputs: list[str] = Field(min_length=1)
    constraints: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("inputs", "constraints", "assumptions", "open_questions")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Listas de investigação não podem conter texto vazio.")
        return [value.strip() for value in values]


class ResearchMetric(ResearchContract):
    name: str = Field(min_length=1)
    direction: Literal["minimize", "maximize"]
    measurement: str = Field(min_length=1)


class SuccessCriterion(ResearchContract):
    metric: str = Field(min_length=1)
    baseline: str = Field(min_length=1)
    # Fração relativa, por exemplo 0.05 significa 5%; média entre seeds.
    min_relative_improvement: Decimal = Field(ge=0, le=1, allow_inf_nan=False)


class ResearchProtocol(ResearchContract):
    question: ResearchQuestionSpec
    method: str = Field(min_length=1)
    baselines: list[str] = Field(min_length=1)
    metrics: list[ResearchMetric] = Field(min_length=1)
    seeds: list[int] = Field(min_length=1)
    success_criteria: str = Field(min_length=1)
    executable_criteria: list[SuccessCriterion] = Field(default_factory=list)
    stopping_rule: str = Field(min_length=1)
    provenance_policy: str = Field(min_length=1)
    limitations: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)

    @field_validator("baselines", "limitations", "assumptions", "open_questions")
    @classmethod
    def reject_blank_items(cls, values: list[str]) -> list[str]:
        if any(not value.strip() for value in values):
            raise ValueError("Listas do protocolo não podem conter texto vazio.")
        return [value.strip() for value in values]

    @model_validator(mode="after")
    def validate_experiment(self) -> "ResearchProtocol":
        # Uma seed repetida não representa uma repetição independente.
        if len(self.seeds) != len(set(self.seeds)):
            raise ValueError("As seeds devem ser únicas.")
        if any(seed < 0 for seed in self.seeds):
            raise ValueError("As seeds devem ser não negativas.")
        names = [metric.name.casefold() for metric in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError("Os nomes das métricas devem ser únicos.")
        pairs = [(item.metric, item.baseline) for item in self.executable_criteria]
        if len(pairs) != len(set(pairs)):
            raise ValueError("Critérios executáveis repetidos.")
        for item in self.executable_criteria:
            if item.metric not in {metric.name for metric in self.metrics} or item.baseline not in self.baselines:
                raise ValueError("Critério refere métrica ou baseline desconhecida.")
        for values in (self.baselines, self.question.inputs):
            if any(not value.strip() for value in values):
                raise ValueError("Baselines e inputs não podem conter texto vazio.")
        return self
