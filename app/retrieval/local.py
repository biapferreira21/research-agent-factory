"""Índice lexical em memória; fontes selecionadas explicitamente pelo chamador."""
import hashlib
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Source(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", str_strip_whitespace=True)
    path: str = Field(min_length=1)
    scope: Literal["global", "domain", "project"]
    domain: str | None = Field(default=None, min_length=1)
    project: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def scope_matches(self):
        if self.scope == "global" and (self.domain or self.project):
            raise ValueError("Fonte global não pertence a um domínio ou projeto.")
        if self.scope == "domain" and (not self.domain or self.project):
            raise ValueError("Fonte de domínio requer apenas domain.")
        if self.scope == "project" and not self.project:
            raise ValueError("Fonte de projeto requer project.")
        return self


class Evidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source: Source
    sha256: str
    first_line: int
    last_line: int
    text: str


class SearchHit(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    evidence: Evidence
    matched_terms: tuple[str, ...]
    score: float


def terms(text: str) -> set[str]:
    """Palavras Unicode, sem distinguir maiúsculas; sem stemming ou sinónimos."""
    return set(re.findall(r"\w+", text.casefold()))


class LocalIndex:
    def __init__(self, root: Path, sources: list[Source], *, lines_per_chunk: int = 20):
        if not 1 <= lines_per_chunk <= 200:
            raise ValueError("lines_per_chunk deve estar entre 1 e 200.")
        root = root.resolve(strict=True)
        chunks = []
        seen = set()
        for source in sources:
            source = Source.model_validate(source.model_dump())
            relative = Path(source.path)
            if relative.is_absolute() or ".." in relative.parts or ":" in source.path:
                raise ValueError("Usar caminhos relativos dentro da pasta de fontes.")
            path = (root / relative).resolve(strict=True)
            if not path.is_relative_to(root):
                raise ValueError("Fonte fora da pasta autorizada.")
            if path in seen:
                raise ValueError("Fonte repetida, mesmo que tenha outro scope.")
            seen.add(path)
            if path.suffix.lower() not in {".txt", ".md"}:
                raise ValueError("Nesta etapa apenas texto UTF-8 .txt ou .md.")
            with path.open("rb") as handle:
                raw = handle.read(1_000_001)
            if len(raw) > 1_000_000:
                raise ValueError("Fonte excede 1 MB.")
            digest = hashlib.sha256(raw).hexdigest()
            lines = raw.decode("utf-8-sig").splitlines()
            for offset in range(0, len(lines), lines_per_chunk):
                text = "\n".join(lines[offset:offset + lines_per_chunk])
                if text.strip():
                    chunks.append(Evidence(source=source, sha256=digest,
                                           first_line=offset + 1,
                                           last_line=min(offset + lines_per_chunk, len(lines)), text=text))
        self.chunks = tuple(chunks)

    def search(self, query: str, *, domain: str | None = None,
               project: str | None = None, limit: int = 5) -> tuple[SearchHit, ...]:
        if not 1 <= limit <= 50:
            raise ValueError("limit deve estar entre 1 e 50.")
        query_terms = terms(query)
        if not query_terms:
            return ()
        hits = []
        for chunk in self.chunks:
            source = chunk.source
            # Filtrar antes de pontuar: nunca recuperar outro projeto por similaridade.
            if source.scope == "domain" and source.domain != domain:
                continue
            if source.scope == "project" and (source.project != project or
                    (source.domain is not None and source.domain != domain)):
                continue
            matched = query_terms & terms(chunk.text)
            if matched:
                hits.append(SearchHit(evidence=chunk, matched_terms=tuple(sorted(matched)),
                                      score=len(matched) / len(query_terms)))
        hits.sort(key=lambda hit: (-hit.score, hit.evidence.source.path, hit.evidence.first_line))
        return tuple(hits[:limit])
