"""Medições individuais; dados sintéticos ficam explicitamente identificados."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResultContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True,
                             allow_inf_nan=False)


class Measurement(ResultContract):
    method: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    seed: int = Field(ge=0, strict=True)
    value: float = Field(strict=True)


class ExperimentResults(ResultContract):
    source_build_id: UUID | None = None
    protocol_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    origin: Literal["synthetic", "executed"]
    candidate_method: str = Field(min_length=1)
    code_version: str = Field(min_length=1)
    dataset_version: str = Field(min_length=1)
    parameters_json: str = Field(min_length=2)
    measurements: tuple[Measurement, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_rows(self):
        import json
        # JSON estruturado sem números não finitos; não executar configurações.
        def reject_constant(value):
            raise ValueError("Parâmetro JSON não finito.")
        def finite_float(value):
            import math
            result = float(value)
            if not math.isfinite(result):
                reject_constant(value)
            return result
        if not isinstance(json.loads(self.parameters_json, parse_constant=reject_constant, parse_float=finite_float), dict):
            raise ValueError("Parâmetros devem ser um objeto JSON.")
        keys = [(row.method, row.metric, row.seed) for row in self.measurements]
        if len(keys) != len(set(keys)):
            raise ValueError("Medição repetida para método/métrica/seed.")
        return self
