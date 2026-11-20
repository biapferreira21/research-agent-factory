import hashlib

import pytest
from pydantic import ValidationError

from app.retrieval.local import LocalIndex, Source


def test_scope_filtering_and_provenance(tmp_path):
    sources = []
    for name, scope, extra in [
        ("global", "global", {}), ("stats", "domain", {"domain": "stats"}),
        ("other", "domain", {"domain": "other"}),
        ("a", "project", {"project": "a"}), ("b", "project", {"project": "b"}),
    ]:
        (tmp_path / f"{name}.txt").write_text("Comparar baseline\nmedir erro", encoding="utf-8")
        sources.append(Source(path=f"{name}.txt", scope=scope, **extra))
    index = LocalIndex(tmp_path, sources, lines_per_chunk=1)
    hits = index.search("BASELINE", domain="stats", project="a")
    assert {hit.evidence.source.path for hit in hits} == {"global.txt", "stats.txt", "a.txt"}
    assert all(hit.evidence.first_line == hit.evidence.last_line == 1 for hit in hits)
    assert hits[0].evidence.sha256 == hashlib.sha256((tmp_path / "a.txt").read_bytes()).hexdigest()
    assert len(index.search("baseline")) == 1


def test_snapshot_ranking_empty_and_limit(tmp_path):
    path = tmp_path / "notes.md"
    path.write_text("baseline erro\nbaseline\nnada", encoding="utf-8")
    index = LocalIndex(tmp_path, [Source(path="notes.md", scope="global")], lines_per_chunk=1)
    path.write_text("alterado", encoding="utf-8")
    hits = index.search("baseline erro", limit=1)
    assert hits[0].score == 1
    assert hits[0].evidence.text == "baseline erro"
    assert index.search("ausente") == index.search("!!!") == ()


@pytest.mark.parametrize("path", ["../outside.txt", "C:/outside.txt", "note.txt:secret"])
def test_path_escape_rejected(tmp_path, path):
    with pytest.raises(ValueError):
        LocalIndex(tmp_path, [Source(path=path, scope="global")])


def test_duplicate_source_cannot_change_scope(tmp_path):
    (tmp_path / "n.txt").write_text("segredo")
    with pytest.raises(ValueError, match="repetida"):
        LocalIndex(tmp_path, [Source(path="n.txt", scope="project", project="a"),
                              Source(path="n.txt", scope="global")])


@pytest.mark.parametrize("kwargs", [{"scope": "domain"}, {"scope": "project"},
                                   {"scope": "global", "project": "a"}])
def test_invalid_scope(kwargs):
    with pytest.raises(ValidationError):
        Source(path="n.txt", **kwargs)


def test_structured_results_are_not_flattened(tmp_path):
    (tmp_path / "results.json").write_text('{"accuracy": 0.9}')
    with pytest.raises(ValueError, match="UTF-8"):
        LocalIndex(tmp_path, [Source(path="results.json", scope="global")])
