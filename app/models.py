from langchain_core.language_models.chat_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_openrouter import ChatOpenRouter

from app.config import get_settings
from app.telemetry.build import active_build
from app.telemetry.callbacks import UsageCallback
from app.decisions.model_router import route_model


def get_model(*, tool_calling: bool = True, structured_output: bool = False,
              provider: str | None = None, model: str | None = None,
              timeout_seconds: int | None = None) -> BaseChatModel:
    settings = get_settings()
    telemetry = active_build.get()
    configured_model = settings.openrouter_model if settings.model_provider == "openrouter" else settings.openai_model
    selected_provider = telemetry.model_provider if telemetry and telemetry.model_provider else settings.model_provider
    selected_model = telemetry.model if telemetry and telemetry.model else configured_model
    provider_name = provider or selected_provider
    model_name = model or (selected_model if provider_name == selected_provider else "")
    if not model_name:
        raise RuntimeError("A model provider and model are required")
    entry = route_model(provider_name, model_name,
                        tool_calling=tool_calling, structured_output=structured_output)
    callbacks = [UsageCallback(telemetry, entry.provider, entry.model, entry)] if telemetry else None
    # ChatOpenRouter expects milliseconds, while the factory configuration is
    # deliberately expressed in seconds for readability. Retries are disabled
    # here so a failed interactive call releases its project lock immediately.
    retries = 0
    timeout_in_seconds = int(timeout_seconds or getattr(settings, "model_build_timeout_seconds", 150))

    if entry.provider == "openai":
        if not settings.openai_api_key:
            raise RuntimeError(
                "OPENAI_API_KEY nao configurada"
            )

        return ChatOpenAI(
            model=entry.model,
            api_key=settings.openai_api_key,
            temperature=0,
            timeout=timeout_in_seconds,
            max_retries=retries,
            callbacks=callbacks,
            max_tokens=entry.max_output_tokens,
        )

    if entry.provider == "openrouter":
        if not settings.openrouter_api_key:
            raise RuntimeError(
                "OPENROUTER_API_KEY nao configurada"
            )

        return ChatOpenRouter(
            model=entry.model,
            api_key=settings.openrouter_api_key,
            temperature=0,
            # langchain-openrouter forwards this value to OpenRouter as
            # timeout_ms; langchain-openai expects seconds.
            timeout=timeout_in_seconds * 1000,
            max_retries=retries,
            callbacks=callbacks,
            max_tokens=entry.max_output_tokens,
        )

    raise RuntimeError(
        f"Provider desconhecido: {settings.model_provider}"
    )

