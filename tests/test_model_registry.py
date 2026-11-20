from datetime import date, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.registry.models import ModelPricing, ModelRegistry, ModelRequirements, RegisteredModel, RegistryError


def make_entry(**changes):
    data = dict(
        provider="openrouter", model="test/model", enabled=True,
        context_window=10000, max_output_tokens=1000, tool_calling=True,
        pricing=ModelPricing(input_usd_per_million="2", output_usd_per_million="8",
                             source="test-only", checked_on=date.today()),
    )
    data.update(changes)
    return RegisteredModel(**data)


def test_price_math_uses_per_million_not_per_token():
    entry = make_entry()
    assert entry.pricing.estimate(1000, 500) == Decimal("0.006")
    assert entry.reservation() == Decimal("0.028")


@pytest.mark.parametrize("input_tokens,output_tokens", [(-1, 2), (1.5, 2), (True, 2), (1, -2)])
def test_invalid_token_counts(input_tokens, output_tokens):
    with pytest.raises(ValueError):
        make_entry().pricing.estimate(input_tokens, output_tokens)


def test_duplicate_catalog_keys_are_rejected():
    with pytest.raises(ValidationError):
        ModelRegistry(models=(make_entry(), make_entry()))


def test_same_id_on_different_provider_is_distinct():
    registry = ModelRegistry(models=(make_entry(), make_entry(provider="openai")))
    assert len(registry.models) == 2


@pytest.mark.parametrize("changes", [
    {"context_window": 0}, {"max_output_tokens": 10001}, {"model": ""},
])
def test_invalid_model_limits_are_rejected(changes):
    with pytest.raises(ValidationError):
        make_entry(**changes)


@pytest.mark.parametrize("price", ["-1", "NaN", "Infinity"])
def test_invalid_prices_are_rejected(price):
    with pytest.raises(ValidationError):
        ModelPricing(input_usd_per_million=price, output_usd_per_million="1",
                     source="test", checked_on=date.today())


def test_disabled_models_and_routers_are_not_implicitly_approved():
    registry = ModelRegistry(models=(make_entry(enabled=False), make_entry(model="test/router", is_router=True)))
    assert registry.candidates(ModelRequirements()) == []
    assert len(registry.candidates(ModelRequirements(allow_router=True))) == 1


@pytest.mark.parametrize("model", ["openrouter/free", "vendor/model:free", "vendor/zero-price"])
def test_free_models_are_rejected_even_when_enabled(model):
    pricing = ModelPricing(
        input_usd_per_million="0", output_usd_per_million="0",
        source="test", checked_on=date.today(),
    )
    registry = ModelRegistry(models=(make_entry(model=model, pricing=pricing),))

    assert registry.candidates(ModelRequirements(allow_router=True)) == []
    with pytest.raises(RegistryError, match="Apenas modelos pagos"):
        registry.require("openrouter", model, ModelRequirements(allow_router=True))


@pytest.mark.parametrize("requirements", [
    ModelRequirements(structured_output=True), ModelRequirements(provider="openai"),
    ModelRequirements(min_context_tokens=10001), ModelRequirements(max_reservation_usd="0.027"),
])
def test_incompatible_candidates_are_filtered(requirements):
    assert ModelRegistry(models=(make_entry(),)).candidates(requirements) == []


def test_tool_calling_and_exact_budget_boundary():
    registry = ModelRegistry(models=(make_entry(), make_entry(model="test/no-tools", tool_calling=False)))
    assert [entry.model for entry in registry.candidates(
        ModelRequirements(tool_calling=True, max_reservation_usd="0.028")
    )] == ["test/model"]


def test_expired_and_future_prices_are_not_eligible():
    today = date.today()
    registry = ModelRegistry(models=(make_entry(),))
    assert len(registry.candidates(ModelRequirements(), today=today + timedelta(days=29))) == 1
    assert registry.candidates(ModelRequirements(), today=today + timedelta(days=30)) == []
    assert registry.candidates(ModelRequirements(), today=today - timedelta(days=1)) == []


def test_missing_model_never_falls_back_to_another():
    registry = ModelRegistry(models=(make_entry(),))
    with pytest.raises(RegistryError):
        registry.require("openrouter", "unapproved", ModelRequirements())


def test_catalog_round_trip(tmp_path):
    registry = ModelRegistry(models=(make_entry(),))
    path = tmp_path / "catalog.json"
    path.write_text(registry.model_dump_json(), encoding="utf-8")
    assert ModelRegistry.load(path) == registry
