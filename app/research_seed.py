"""Create the project-scoped research starter pack used by generated agents."""

from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import quote_plus

from app.research_web import download_public
from app.wiki import ProjectWiki


def _safe_arxiv_id(url: str) -> str | None:
    match = re.fullmatch(
        r"https://arxiv\.org/abs/([0-9.]+(?:v[0-9]+)?|[a-zA-Z.-]+/[0-9]+(?:v[0-9]+)?)",
        url.strip(),
    )
    return match.group(1) if match else None


def _starter_markdown(question: str, query: str, papers: list[dict], errors: list[dict]) -> str:
    created = datetime.now(timezone.utc).isoformat()
    rows = [
        "# Research starter pack",
        "",
        f"- Research brief: {question}",
        f"- Search query: {query}",
        f"- Generated: {created}",
        "- Automated indexes: arXiv, Crossref, OpenAlex, Semantic Scholar",
        f"- Google Scholar verification: https://scholar.google.com/scholar?q={quote_plus(query)}",
        "",
        "> Candidate literature must be screened for methodological fit before it is treated as evidence.",
        "",
        "## Candidate literature",
        "",
    ]
    for number, paper in enumerate(papers, 1):
        summary = " ".join(str(paper.get("summary", "")).split())
        rows.extend([
            f"### {number}. {paper.get('title', 'Untitled')}",
            "",
            f"- Citation key: `{paper.get('citation', '')}`",
            f"- Provider: {paper.get('provider', '')}",
            f"- Published: {paper.get('published', '')}",
            f"- URL: {paper.get('url', '')}",
            f"- DOI: {paper.get('doi', '')}" if paper.get("doi") else "",
            "",
            summary or "Abstract unavailable from this index.",
            "",
        ])
    if errors:
        rows.extend(["## Search notes", "", "```json", json.dumps(errors, indent=2), "```", ""])
    return "\n".join(row for row in rows if row is not None)


def seed_research_memory(store, project_id: str, question: str, *, searcher,
                         progress=None, downloader=download_public, max_pdfs: int = 2) -> dict:
    """Search scholarly indexes, add a cited Markdown pack and cache open arXiv PDFs."""
    manifest_path = store.directory(project_id) / "research_seed.json"
    if manifest_path.is_file() and not manifest_path.is_symlink():
        try:
            existing = json.loads(manifest_path.read_text(encoding="utf-8"))
            if existing.get("question") == question and existing.get("papers"):
                if progress is not None:
                    progress("Reusing the indexed research base")
                return existing
        except (OSError, ValueError):
            pass
    query, papers, errors = searcher(store, project_id, {"question": question}, progress)
    if not papers:
        raise RuntimeError("No scholarly sources were retrieved; the research agent was not built")
    digest = hashlib.sha256((question + "\n" + query).encode("utf-8")).hexdigest()[:12]
    markdown = _starter_markdown(question, query, papers, errors)
    pack = store.add_document(project_id, f"research-starter-{digest}.md", markdown.encode("utf-8"))
    pdfs: list[dict] = []
    for paper in papers:
        if len(pdfs) >= max_pdfs:
            break
        identifier = _safe_arxiv_id(str(paper.get("url", "")))
        if not identifier:
            continue
        pdf_url = f"https://arxiv.org/pdf/{identifier}"
        if progress is not None:
            progress(f"Caching arXiv PDF {identifier}")
        try:
            raw = downloader(pdf_url, max_bytes=20_000_000)
            if not raw.startswith(b"%PDF"):
                raise ValueError("arXiv response is not a PDF")
            added = store.add_document(project_id, f"arxiv-{identifier.replace('/', '-')}.pdf", raw)
            pdfs.append({"citation": paper.get("citation"), "url": pdf_url, **added})
        except Exception as error:
            errors.append({"provider": "arxiv_pdf", "citation": paper.get("citation"),
                           "error": type(error).__name__})
    manifest = {
        "format_version": 1,
        "question": question,
        "query": query,
        "providers": ["arxiv", "crossref", "openalex", "semantic_scholar"],
        "google_scholar_verification_url": "https://scholar.google.com/scholar?q=" + quote_plus(query),
        "papers": papers,
        "errors": errors,
        "starter_document": pack,
        "pdf_documents": pdfs,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    if not pack.get("duplicate"):
        ProjectWiki(store.directory(project_id)).add(
            "Research base prepared",
            f"{len(papers)} candidate papers indexed; {len(pdfs)} arXiv PDFs cached.\n\nQuery: `{query}`",
            kind="source",
        )
    return manifest
