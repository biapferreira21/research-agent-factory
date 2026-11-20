"""Clientes MCP para os dois servidores próprios. Nenhum comando arbitrário."""
import asyncio
from datetime import timedelta
from pathlib import Path
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def call_local_mcp(kind, root, project_id, tool, arguments):
    if kind not in {"bm25", "web"}:
        raise ValueError("MCP não aprovado")
    allowed = {"bm25": {"search", "list_documents", "read_chunk"}, "web": {"web_search", "read_url"}}
    if tool not in allowed[kind]:
        raise ValueError("Ferramenta não aprovada")
    args = ["-m", "app.mcp_server", kind, "--root", str(Path(root).resolve())]
    if kind == "bm25":
        from uuid import UUID
        args += ["--project-id", str(UUID(project_id))]
    params = StdioServerParameters(command=sys.executable, args=args, cwd=str(Path(__file__).resolve().parents[1]))
    async with asyncio.timeout(45):
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=40)) as session:
                await session.initialize()
                result = await session.call_tool(tool, arguments)
                if result.isError:
                    raise RuntimeError("O MCP devolveu erro")
                return [item.text for item in result.content if item.type == "text"]


def project_tools(root, project_id, *, allow_web=False, allowed_tools=None):
    """Ferramentas LangChain com projeto fixo; root/project_id não são argumentos do modelo."""
    from langchain.tools import tool

    @tool
    def search_documents(query: str, limit: int = 6) -> list[str]:
        """Search the bound research project's documents via BM25 MCP, returning citations."""
        return asyncio.run(call_local_mcp("bm25", root, project_id, "search", {"query": query, "limit": limit}))

    @tool
    def read_document_chunk(citation: str) -> list[str]:
        """Read a cited source chunk belonging to this project via MCP."""
        return asyncio.run(call_local_mcp("bm25", root, project_id, "read_chunk", {"citation": citation}))

    @tool
    def search_web(query: str, limit: int = 5, provider: str = "crossref") -> list[str]:
        """Search approved arXiv, Crossref, OpenAlex or Semantic Scholar providers."""
        return asyncio.run(call_local_mcp("web", root, project_id, "web_search", {"query": query, "limit": limit, "provider": provider}))

    available = {"factory-bm25/search": search_documents, "factory-bm25/read_chunk": read_document_chunk}
    if allow_web:
        available["factory-web/web_search"] = search_web
    chosen = list(available) if allowed_tools is None else allowed_tools
    if any(name not in available for name in chosen):
        raise ValueError("Ferramenta fora das permissões do runtime")
    return [available[name] for name in chosen]
