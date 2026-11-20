"""Carregar um catálogo por build e guardar a versão usada para auditoria."""

from app.config import get_model_registry_path, get_settings
from app.registry.models import ModelRegistry, ModelRequirements, RegisteredModel, RegistryError
from app.telemetry.build import active_build
from app.telemetry.costs import BudgetBlocked


def get_registry() -> ModelRegistry:
    telemetry = active_build.get()
    if telemetry is not None and telemetry.model_registry is not None:
        return telemetry.model_registry
    registry = ModelRegistry.load(get_model_registry_path())
    if telemetry is not None:
        telemetry.model_registry = registry
        (telemetry.directory / "model_registry.json").write_text(
            registry.model_dump_json(indent=2), encoding="utf-8",
        )
    return registry


def require_model(provider: str, model: str, *, tool_calling: bool = True,
                  structured_output: bool = False) -> RegisteredModel:
    requirements = ModelRequirements(
        provider=provider, tool_calling=tool_calling, structured_output=structured_output,
        allow_router=get_settings().allow_model_router,
    )
    try:
        return get_registry().require(provider, model, requirements)
    except RegistryError as error:
        raise BudgetBlocked(str(error)) from error
