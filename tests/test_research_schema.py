import pytest
from pydantic import ValidationError

from app.schemas.research import ResearchProtocol, ResearchQuestionSpec
from research_demo import create_example_protocol


def test_protocol_round_trip():
    protocol = create_example_protocol()
    assert ResearchProtocol.model_validate_json(protocol.model_dump_json()) == protocol


@pytest.mark.parametrize("field,value", [
    ("seeds", []),
    ("seeds", [11, 11]),
    ("seeds", [-1]),
    ("baselines", []),
    ("baselines", ["  "]),
    ("metrics", []),
    ("success_criteria", "  "),
    ("stopping_rule", ""),
    ("provenance_policy", ""),
])
def test_invalid_protocol_is_rejected(field, value):
    data = create_example_protocol().model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(data)


def test_duplicate_metrics_are_rejected():
    data = create_example_protocol().model_dump()
    data["metrics"].append(dict(data["metrics"][0], name="MEAN_ERROR"))
    with pytest.raises(ValidationError):
        ResearchProtocol.model_validate(data)


def test_unknown_fields_are_rejected():
    data = create_example_protocol().question.model_dump()
    data["hypotesis"] = "Erro de escrita"
    with pytest.raises(ValidationError):
        ResearchQuestionSpec.model_validate(data)


def test_defaults_are_not_shared():
    first = create_example_protocol().question
    data = first.model_dump(exclude={"constraints"})
    second = ResearchQuestionSpec.model_validate(data)
    third = ResearchQuestionSpec.model_validate(data)
    second.constraints.append("Novo limite")
    assert third.constraints == []
