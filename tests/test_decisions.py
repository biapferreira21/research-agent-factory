import pytest
from pydantic import ValidationError

from app.decisions.backends import ConfiguredModelBackend, FixedDecisionBackend
from app.decisions.schemas import (
    ChoiceProbability, DecisionPolicy, DecisionRequest, DecisionResponse, DecisionState, ModelChoice,
)
from app.decisions.service import DecisionBlocked, DecisionService


@pytest.fixture
def request_data():
    return DecisionRequest(state=DecisionState(stage="test", preferred_choice_id="a"), candidates=tuple(
        ModelChoice(id=name, provider="fake", model=name, reservation_usd="0", context_window=1000,
                    tool_calling=True, structured_output=False) for name in ("a", "b")
    ))


def test_accepts_candidate_at_exact_confidence_threshold(request_data):
    result = DecisionService(FixedDecisionBackend("a", 0.8)).decide(request_data)
    assert result.choice_id == "a"
    assert not result.used_fallback


def test_unknown_candidate_is_never_rescued_by_fallback(request_data):
    class ForbiddenFallback:
        name = "never"
        def decide(self, request):
            pytest.fail("Invalid responses must not activate fallback")
    service = DecisionService(FixedDecisionBackend("invented", 1.0),
                              policy=DecisionPolicy(on_low_confidence="fallback"), fallback=ForbiddenFallback())
    records = []
    with pytest.raises(DecisionBlocked):
        service.decide(request_data, sink=records.append)
    assert records[0].status == "rejected"
    assert records[0].response is None


def test_low_confidence_blocks_by_default(request_data):
    with pytest.raises(DecisionBlocked, match="Confiança"):
        DecisionService(FixedDecisionBackend("a", 0.79)).decide(request_data)


def test_explicit_fallback_is_validated_and_recorded(request_data):
    records = []
    service = DecisionService(FixedDecisionBackend("b", 0.4),
                              policy=DecisionPolicy(on_low_confidence="fallback"), fallback=ConfiguredModelBackend())
    result = service.decide(request_data, sink=records.append)
    assert result.choice_id == "a"
    assert result.used_fallback
    assert [(record.attempt, record.status) for record in records] == [
        ("primary", "low_confidence"), ("fallback", "accepted"),
    ]


@pytest.mark.parametrize("fallback", [FixedDecisionBackend("a", 0.4), FixedDecisionBackend("invalid", 1.0)])
def test_failed_fallback_stops_without_a_loop(request_data, fallback):
    records = []
    service = DecisionService(FixedDecisionBackend("a", 0.4),
                              policy=DecisionPolicy(on_low_confidence="fallback"), fallback=fallback)
    with pytest.raises(DecisionBlocked):
        service.decide(request_data, sink=records.append)
    assert len(records) == 2


def test_wrong_request_id_is_rejected(request_data):
    class WrongRequest:
        name = "wrong_request"
        def decide(self, request):
            return DecisionResponse(request_id="another", choice_id="a", confidence=1.0)
    with pytest.raises(DecisionBlocked):
        DecisionService(WrongRequest()).decide(request_data)


@pytest.mark.parametrize("values", [(("a", .5),), (("a", .5), ("a", .5)),
                                    (("a", .5), ("c", .5)), (("a", .4), ("b", .4))])
def test_invalid_probability_distribution_is_rejected(request_data, values):
    class Backend:
        name = "bad_distribution"
        def decide(self, request):
            return DecisionResponse(request_id=request.request_id, choice_id="a", confidence=.9,
                                    probabilities=tuple(ChoiceProbability(choice_id=key, probability=value) for key, value in values))
    with pytest.raises(DecisionBlocked):
        DecisionService(Backend()).decide(request_data)


def test_valid_distribution_is_preserved(request_data):
    class Backend:
        name = "distribution"
        def decide(self, request):
            return DecisionResponse(request_id=request.request_id, choice_id="a", confidence=.9, probabilities=(
                ChoiceProbability(choice_id="a", probability=.7), ChoiceProbability(choice_id="b", probability=.3),
            ))
    records = []
    DecisionService(Backend()).decide(request_data, sink=records.append)
    assert records[0].response.probabilities[0].probability == .7


@pytest.mark.parametrize("confidence", [-0.1, 1.1, float("nan"), float("inf"), "0.9"])
def test_confidence_must_be_numeric_finite_and_in_range(confidence):
    with pytest.raises(ValidationError):
        DecisionResponse(request_id="id", choice_id="a", confidence=confidence)


def test_empty_candidates_do_not_call_backend(request_data):
    class Forbidden:
        name = "never"
        def decide(self, request):
            pytest.fail("Backend called without candidates")
    with pytest.raises(DecisionBlocked):
        DecisionService(Forbidden()).decide(request_data.model_copy(update={"candidates": ()}))


def test_duplicate_candidate_ids_are_rejected(request_data):
    with pytest.raises(ValidationError):
        DecisionRequest(state=request_data.state, candidates=(request_data.candidates[0], request_data.candidates[0]))


def test_backend_error_is_logged_without_secret(request_data):
    class Broken:
        name = "broken"
        def decide(self, request):
            raise RuntimeError("SECRET")
    records = []
    with pytest.raises(DecisionBlocked):
        DecisionService(Broken()).decide(request_data, sink=records.append)
    assert "SECRET" not in records[0].model_dump_json()
    assert records[0].reason == "backend_error"


def test_unvalidated_response_is_revalidated(request_data):
    class Broken:
        name = "unvalidated"
        def decide(self, request):
            return DecisionResponse.model_construct(request_id=request.request_id, choice_id="a", confidence=2.0)
    with pytest.raises(DecisionBlocked):
        DecisionService(Broken()).decide(request_data)
