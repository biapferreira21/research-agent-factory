"""Validação, filtragem e preços de modelos. Não faz chamadas de rede."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class RegistryError(ValueError):
    pass


class RegistryRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False, str_strip_whitespace=True)


class ModelPricing(RegistryRecord):
    # Só preços de texto simples nesta versão. Não modela descontos nem escalões.
    kind: Literal["flat_text"] = "flat_text"
    input_usd_per_million: Decimal = Field(ge=0)
    output_usd_per_million: Decimal = Field(ge=0)
    request_usd: Decimal = Field(default=Decimal("0"), ge=0)
    source: str = Field(min_length=1)
    checked_on: date
    valid_for_days: int = Field(default=30, ge=1, le=365)

    def is_current(self, today: date | None = None) -> bool:
        age = ((today or date.today()) - self.checked_on).days
        return 0 <= age < self.valid_for_days

    def estimate(self, input_tokens: int, output_tokens: int) -> Decimal:
        if any(type(value) is not int or value < 0 for value in (input_tokens, output_tokens)):
            raise ValueError("Tokens devem ser inteiros não negativos.")
        return self.request_usd + (
            input_tokens * self.input_usd_per_million
            + output_tokens * self.output_usd_per_million
        ) / Decimal("1000000")


class RegisteredModel(RegistryRecord):
    provider: Literal["openai", "openrouter"]
    model: str = Field(min_length=1)
    enabled: bool = False
    is_router: bool = False
    context_window: int = Field(gt=0)
    max_output_tokens: int = Field(gt=0)
    tool_calling: bool = False
    structured_output: bool = False
    pricing: ModelPricing
    notes: str = ""

    @model_validator(mode="after")
    def check_token_limits(self):
        if self.max_output_tokens > self.context_window:
            raise ValueError("O limite de output não pode exceder a janela de contexto.")
        return self

    def reservation(self) -> Decimal:
        # Sobre-reserva deliberada: toda a janela como input + output máximo.
        # Evita fingir que uma contagem local de strings inclui schemas de tools.
        return self.pricing.estimate(self.context_window, self.max_output_tokens)

    def is_free(self) -> bool:
        """Reject free endpoints even if a catalogue entry is accidentally enabled."""
        identifier = self.model.casefold()
        zero_priced = (
            self.pricing.input_usd_per_million == 0
            and self.pricing.output_usd_per_million == 0
            and self.pricing.request_usd == 0
        )
        return identifier == "openrouter/free" or identifier.endswith(":free") or zero_priced


class ModelRequirements(RegistryRecord):
    provider: Literal["openai", "openrouter"] | None = None
    tool_calling: bool = False
    structured_output: bool = False
    min_context_tokens: int = Field(default=1, ge=1)
    allow_router: bool = False
    max_reservation_usd: Decimal | None = Field(default=None, ge=0)


class ModelRegistry(RegistryRecord):
    schema_version: Literal["1.0"] = "1.0"
    models: tuple[RegisteredModel, ...] = ()

    @model_validator(mode="after")
    def unique_models(self):
        keys = [(entry.provider, entry.model) for entry in self.models]
        if len(keys) != len(set(keys)):
            raise ValueError("Provider e model devem identificar uma entrada única.")
        return self

    @classmethod
    def load(cls, path: Path) -> "ModelRegistry":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))

    def candidates(self, requirements: ModelRequirements, *, today: date | None = None) -> list[RegisteredModel]:
        result = []
        for entry in self.models:
            if not entry.enabled or entry.is_free() or not entry.pricing.is_current(today):
                continue
            if requirements.provider is not None and entry.provider != requirements.provider:
                continue
            if entry.is_router and not requirements.allow_router:
                continue
            if requirements.tool_calling and not entry.tool_calling:
                continue
            if requirements.structured_output and not entry.structured_output:
                continue
            if entry.context_window < requirements.min_context_tokens:
                continue
            if requirements.max_reservation_usd is not None and entry.reservation() > requirements.max_reservation_usd:
                continue
            result.append(entry)
        return result

    def require(self, provider: str, model: str, requirements: ModelRequirements) -> RegisteredModel:
        for entry in self.candidates(requirements):
            if entry.provider == provider and entry.model == model:
                return entry
        raise RegistryError(
            f"Modelo não elegível: {provider}/{model}. Apenas modelos pagos, nomeados, aprovados e com preços atuais são permitidos."
        )
