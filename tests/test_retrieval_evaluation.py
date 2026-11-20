import pytest

from app.retrieval.evaluation import RetrievalCase, evaluate
from app.retrieval.local import LocalIndex, Source


@pytest.fixture
def index(tmp_path):
    for name, text in [("a", "baseline\nbaseline"), ("b", "baseline erro")]:
        (tmp_path / f"{name}.txt").write_text(text)
    return LocalIndex(tmp_path, [Source(path=f"{name}.txt", scope="global") for name in ("a", "b")],
                      lines_per_chunk=1)


def test_extra_sources_lower_precision_and_duplicate_chunks_count_once(index):
    report = evaluate(index, [RetrievalCase(name="case", query="baseline", expected_sources=("a.txt",))])
    result = report["results"][0]
    assert result["precision"] == 0.5
    assert result["recall"] == 1
    assert result["unexpected_sources"] == ["b.txt"]
    assert report["passed_count"] == 0


def test_missing_evidence_after_context_cap_is_a_failure(index):
    report = evaluate(index, [RetrievalCase(name="case", query="erro", expected_sources=("b.txt",))],
                      max_context_chars=2)
    result = report["results"][0]
    assert result["recall"] == 0
    assert result["precision"] is None
    assert result["snapshot"]["skipped_for_size"] == 1
    assert result["missing_sources"] == ["b.txt"]


def test_negative_cases_and_undefined_metrics(index):
    report = evaluate(index, [RetrievalCase(name="negative", query="absent", expected_sources=())])
    assert report["pass_rate"] == 1
    assert report["mean_defined_precision"] is None
    assert report["mean_defined_recall"] is None
    failed = evaluate(index, [RetrievalCase(name="negative", query="erro", expected_sources=())])
    assert failed["pass_rate"] == 0
    assert failed["mean_defined_precision"] == 0


def test_invalid_suite_and_unknown_labels(index):
    with pytest.raises(ValueError):
        evaluate(index, [])
    case = RetrievalCase(name="same", query="baseline", expected_sources=())
    with pytest.raises(ValueError):
        evaluate(index, [case, case])
    with pytest.raises(ValueError, match="ausente"):
        evaluate(index, [RetrievalCase(name="typo", query="baseline", expected_sources=("missing",))])
