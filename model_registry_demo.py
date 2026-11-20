"""Lê o catálogo e demonstra preços fictícios, sem chamar APIs."""

from datetime import date
from decimal import Decimal

from app.config import get_model_registry_path
from app.registry.models import ModelPricing, ModelRegistry, ModelRequirements


if __name__ == "__main__":
    registry = ModelRegistry.load(get_model_registry_path())
    requirements = ModelRequirements(tool_calling=True, allow_router=True, max_reservation_usd=Decimal("1"))
    print("Modelos elegíveis no catálogo local:")
    for entry in registry.candidates(requirements):
        print(f"- {entry.provider}/{entry.model}: reserva USD {entry.reservation()}")

    # Estes preços são inventados para ensinar a fórmula. Não entram no catálogo.
    example = ModelPricing(
        input_usd_per_million=Decimal("2"), output_usd_per_million=Decimal("8"),
        source="Exemplo didático, não é um preço comercial", checked_on=date.today(),
    )
    print(f"\nExemplo fictício: 1000 tokens de input + 500 de output = USD {example.estimate(1000, 500)}")
