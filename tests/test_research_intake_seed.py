from io import BytesIO

import httpx
from fastapi.testclient import TestClient

from app.projects import ProjectStore
from app.research_intake import assess_research_brief, compile_research_brief
from app.research_seed import seed_research_memory
from app.research_web import search_papers
from app.web import create_app


def test_research_intake_blocks_generic_agent_requests_and_accepts_a_question():
    assert not assess_research_brief("Create a research agent").ready
    status = assess_research_brief(
        "How does optimizer choice affect post-training neural network compression at matched accuracy?"
    )
    assert status.ready
    assert status.missing == ()


def test_research_brief_compiles_the_intake_conversation_without_duplicates():
    messages = [
        {"role": "user", "content": "Compare Adam and SGD."},
        {"role": "assistant", "content": "Which outcome?"},
        {"role": "user", "content": "Measure pruning compression at matched accuracy."},
    ]
    brief = compile_research_brief("Neural network optimization", messages, "Compare Adam and SGD.")
    assert brief.count("Compare Adam and SGD.") == 1
    assert "matched accuracy" in brief


def test_live_build_endpoint_refuses_to_create_an_agent_before_intake_is_ready(tmp_path):
    application = create_app(tmp_path)
    with TestClient(application) as client:
        client.headers["x-factory-token"] = client.get("/api/session").json()["token"]
        project = client.post("/api/projects", json={
            "name": "Vague", "question": "Build a research agent", "domain": "general",
        }).json()
        response = client.post(f"/api/projects/{project['id']}/build", json={"mode": "live"})
        assert response.status_code == 400
        assert "RESEARCH_BRIEF_INCOMPLETE" in response.json()["detail"]
        assert client.get(f"/api/projects/{project['id']}").json()["research_status"]["ready"] is False


def _one_page_pdf() -> bytes:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 200 200] /Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length 44 >>\nstream\nBT /F1 12 Tf 20 100 Td (Research evidence) Tj ET\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    target = BytesIO()
    target.write(b"%PDF-1.4\n")
    offsets = [0]
    for number, obj in enumerate(objects, 1):
        offsets.append(target.tell())
        target.write(f"{number} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = target.tell()
    target.write(f"xref\n0 {len(objects)+1}\n".encode())
    target.write(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        target.write(f"{offset:010d} 00000 n \n".encode())
    target.write(f"trailer\n<< /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return target.getvalue()


def test_research_seed_adds_ranked_memory_and_arxiv_pdf(tmp_path):
    store = ProjectStore(tmp_path)
    project = store.create("Compression", "How does optimizer choice affect neural network compression?")
    calls = []

    def searcher(*args):
        return "optimizer neural network compression", [{
            "citation": "arxiv:2401.00001", "title": "Compression and Optimizers",
            "url": "https://arxiv.org/abs/2401.00001", "summary": "A comparative study.",
            "published": "2024", "provider": "arxiv", "doi": None,
        }], []

    def downloader(url, **kwargs):
        calls.append((url, kwargs["max_bytes"]))
        return _one_page_pdf()

    result = seed_research_memory(
        store, project["id"], project["question"], searcher=searcher, downloader=downloader,
    )
    names = {document["name"] for document in store.documents(project["id"])}
    assert any(name.startswith("research-starter-") for name in names)
    assert "arxiv-2401.00001.pdf" in names
    assert result["papers"][0]["citation"] == "arxiv:2401.00001"
    assert result["google_scholar_verification_url"].startswith("https://scholar.google.com/")
    assert calls == [("https://arxiv.org/pdf/2401.00001", 20_000_000)]
    assert store.search(project["id"], "optimizer compression")


def test_openalex_and_semantic_scholar_are_supported_public_indexes():
    def responder(request):
        if request.url.host == "api.openalex.org":
            return httpx.Response(200, json={"results": [{
                "id": "https://openalex.org/W1", "display_name": "Open paper", "doi": "https://doi.org/10/x",
                "publication_year": 2025, "abstract_inverted_index": {"Useful": [0], "evidence": [1]},
                "primary_location": {"landing_page_url": "https://example.org/paper", "pdf_url": None},
                "open_access": {"oa_url": None},
            }]})
        return httpx.Response(200, json={"data": [{
            "title": "Semantic paper", "abstract": "Evidence", "url": "https://www.semanticscholar.org/paper/1",
            "year": 2024, "authors": [{"name": "A. Author"}], "externalIds": {"DOI": "10/y"},
            "openAccessPdf": {"url": "https://example.org/paper.pdf"},
        }]})

    transport = httpx.MockTransport(responder)
    openalex = search_papers("compression", provider="openalex", transport=transport)
    semantic = search_papers("compression", provider="semantic_scholar", transport=transport)
    assert openalex[0]["summary"] == "Useful evidence"
    assert openalex[0]["doi"] == "10/x"
    assert semantic[0]["authors"] == ["A. Author"]
    assert semantic[0]["pdf_url"].endswith(".pdf")
