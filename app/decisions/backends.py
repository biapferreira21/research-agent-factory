from app.decisions.schemas import DecisionRequest, DecisionResponse


class ConfiguredModelBackend:
    """Regra local: preservar o modelo configurado. Não representa confiança estatística."""
    name = "configured_model_rule"

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        return DecisionResponse(request_id=request.request_id,
                                choice_id=request.state.preferred_choice_id, confidence=1.0)


class FixedDecisionBackend:
    """Decisor falso para exercícios e testes; não comunica com serviços."""
    name = "fake_fixed_decision"

    def __init__(self, choice_id: str, confidence: float = 1.0):
        self.choice_id = choice_id
        self.confidence = confidence

    def decide(self, request: DecisionRequest) -> DecisionResponse:
        return DecisionResponse(request_id=request.request_id, choice_id=self.choice_id,
                                confidence=self.confidence)
