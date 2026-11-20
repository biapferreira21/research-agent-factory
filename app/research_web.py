"""Pesquisa científica pública com fornecedores fixos; não aceita hosts arbitrários."""
from html import unescape
import re
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx


ALLOWED_HOSTS = {
    "arxiv.org", "export.arxiv.org", "api.crossref.org", "api.openalex.org",
    "api.semanticscholar.org", "en.wikipedia.org",
}


def download_public(url, *, transport=None, max_bytes=2_000_000):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname not in ALLOWED_HOSTS or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("URL fora dos domínios públicos aprovados")
    with httpx.Client(timeout=20, follow_redirects=False, trust_env=False, transport=transport) as client:
        with client.stream("GET", url, headers={"User-Agent": "ResearchAgentFactory/0.1 (local research tool)"}) as response:
            response.raise_for_status()
            raw = bytearray()
            for chunk in response.iter_bytes():
                raw.extend(chunk)
                if len(raw) > max_bytes:
                    raise ValueError("Public response exceeds the configured size limit")
            return bytes(raw)


def read_public(url, *, transport=None):
    return download_public(url, transport=transport).decode("utf-8", errors="replace")


def _openalex_abstract(index):
    if not isinstance(index, dict):
        return ""
    positioned = [(position, word) for word, positions in index.items() for position in positions]
    return " ".join(word for _, word in sorted(positioned))


def search_papers(query, limit=5, provider="crossref", *, transport=None):
    if not query.strip() or len(query) > 1000 or not 1 <= limit <= 20:
        raise ValueError("Pergunta não vazia até 1000 caracteres; limite entre 1 e 20")
    from urllib.parse import urlencode
    if provider == "arxiv":
        try:
            body = read_public("https://export.arxiv.org/api/query?" + urlencode({"search_query": "all:" + query,
                               "start": 0, "max_results": limit}), transport=transport)
        except httpx.HTTPStatusError as error:
            if error.response.status_code != 406:
                raise
            # The public Atom API intermittently returns 406 for valid searches.
            # The official HTML search accepts pages of 50; return only the requested count.
            from bs4 import BeautifulSoup
            html = read_public("https://arxiv.org/search/?" + urlencode({"query": query,
                               "searchtype": "all", "abstracts": "show",
                               "order": "-announced_date_first", "size": 50}), transport=transport)
            soup = BeautifulSoup(html, "html.parser")
            results = []
            for item in soup.select("li.arxiv-result")[:limit]:
                link = item.select_one("p.list-title a[href^='https://arxiv.org/abs/']")
                title = item.select_one("p.title")
                if link is None or title is None:
                    continue
                summary = item.select_one("p.abstract span.abstract-full") or item.select_one("p.abstract")
                date = item.select_one("p.is-size-7")
                results.append({"title": title.get_text(" ", strip=True), "url": link["href"],
                                "summary": summary.get_text(" ", strip=True) if summary else "",
                                "provider": "arxiv", "published": date.get_text(" ", strip=True) if date else ""})
            return results
        tree = ET.fromstring(body)
        ns = {"a": "http://www.w3.org/2005/Atom"}
        return [{"title": " ".join(entry.findtext("a:title", "", ns).split()),
                 "url": entry.findtext("a:id", "", ns).replace("http://", "https://"),
                 "summary": entry.findtext("a:summary", "", ns), "provider": "arxiv",
                 "published": entry.findtext("a:published", "", ns)} for entry in tree.findall("a:entry", ns)]
    if provider == "openalex":
        import json
        data = json.loads(read_public("https://api.openalex.org/works?" + urlencode({
            "search": query, "per-page": limit,
            "select": "id,display_name,doi,publication_year,abstract_inverted_index,primary_location,open_access",
        }), transport=transport))
        results = []
        for item in data.get("results", []):
            location = item.get("primary_location") or {}
            oa = item.get("open_access") or {}
            results.append({"title": item.get("display_name") or "Untitled",
                            "url": location.get("landing_page_url") or item.get("id", ""),
                            "pdf_url": location.get("pdf_url") or oa.get("oa_url"),
                            "doi": str(item.get("doi") or "").removeprefix("https://doi.org/"),
                            "summary": _openalex_abstract(item.get("abstract_inverted_index")),
                            "provider": "openalex", "published": item.get("publication_year", "")})
        return results
    if provider == "semantic_scholar":
        import json
        data = json.loads(read_public("https://api.semanticscholar.org/graph/v1/paper/search?" + urlencode({
            "query": query, "limit": limit,
            "fields": "title,abstract,url,year,authors,externalIds,openAccessPdf",
        }), transport=transport))
        results = []
        for item in data.get("data", []):
            external = item.get("externalIds") or {}
            pdf = item.get("openAccessPdf") or {}
            results.append({"title": item.get("title") or "Untitled", "url": item.get("url", ""),
                            "pdf_url": pdf.get("url"), "doi": external.get("DOI"),
                            "summary": item.get("abstract") or "", "provider": "semantic_scholar",
                            "published": item.get("year", ""),
                            "authors": [author.get("name", "") for author in item.get("authors", [])]})
        return results
    if provider != "crossref":
        raise ValueError("Provider must be arxiv, crossref, openalex or semantic_scholar")
    import json
    data = json.loads(read_public("https://api.crossref.org/works?" + urlencode({"query": query, "rows": limit}), transport=transport))
    return [{"title": item.get("title", ["Sem título"])[0], "url": item.get("URL", ""),
             "doi": item.get("DOI"), "summary": unescape(re.sub("<[^>]+>", "", item.get("abstract", ""))),
             "provider": "crossref", "published": item.get("published", {}).get("date-parts", [])}
            for item in data["message"]["items"]]
