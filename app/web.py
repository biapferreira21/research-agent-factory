"""Interface local da factory: projetos, documentos, RAG, skills e builds."""
from contextlib import asynccontextmanager
from decimal import Decimal
import json
from pathlib import Path
import secrets
import threading
from urllib.parse import urlsplit

from fastapi import FastAPI, BackgroundTasks, File, UploadFile, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field, model_validator
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import PROJECT_ROOT, get_allowed_hosts, get_settings
from app.integrations import IntegrationStore, PROVIDERS
from app.interface_harness import describe_interface_harness
from app.obsidian import ObsidianBridge
from app.projects import ProjectStore
from app.registry.skills import SkillLibrary
from app.project_runtime import run_build, select_project_skills, chat, agent_chat
from app.research_intake import assess_research_brief, compile_research_brief
from app.wiki import ProjectWiki
from app.version import VERSION


def build_clarification(result: dict | None) -> str | None:
    """Return the concise intake question from a scientifically blocked build."""
    if not isinstance(result, dict) or result.get("status") != "blocked":
        return None
    for raw in result.get("errors") or []:
        message = str(raw).strip()
        for prefix in ("Falta esclarecer a pergunta:", "Falta esclarecer o protocolo:"):
            if message.startswith(prefix):
                question = message.removeprefix(prefix).strip()
                return "INPUT_REQUIRED: " + question if question else None
    return None


class ProjectInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=150)
    question: str = Field(min_length=1, max_length=10000)
    domain: str = Field(default="general", max_length=200)


class QueryInput(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    limit: int = Field(default=6, ge=1, le=20)
    mode: str = "sources"
    provider: str = "crossref"
    model_provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def complete_model_selection(self):
        if bool(self.model_provider) != bool(self.model):
            raise ValueError("Model provider and model must be selected together")
        return self


class AgentChatInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1, max_length=5000)
    model_provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def complete_model_selection(self):
        if bool(self.model_provider) != bool(self.model):
            raise ValueError("Model provider and model must be selected together")
        return self


class BuildInput(BaseModel):
    mode: str = "demo"
    backend: str = "configured"
    repairs: int = Field(default=1, ge=0, le=5)
    budget_usd: Decimal = Field(default=Decimal("1.00"), ge=Decimal("0.01"), le=Decimal("1.00"), allow_inf_nan=False)
    question: str | None = Field(default=None, min_length=1, max_length=10000)
    model_provider: str | None = None
    model: str | None = None

    @model_validator(mode="after")
    def complete_model_selection(self):
        if bool(self.model_provider) != bool(self.model):
            raise ValueError("Model provider and model must be selected together")
        return self


class WikiInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=160)
    content: str = Field(min_length=1, max_length=50000)
    agent_id: str | None = None


class ProviderKeyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_key: str = Field(min_length=20, max_length=500)
    persist: bool = True


class ObsidianInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: str = Field(min_length=1, max_length=1000)


def provider_key_configured(provider: str) -> bool:
    settings = get_settings()
    if provider == "openrouter":
        return bool(settings.openrouter_api_key)
    if provider == "openai":
        return bool(settings.openai_api_key)
    return False


def agent_chat_readiness(spec):
    if not spec or not spec.get("model"):
        return False, "This build has no research-agent model specification."
    model = spec["model"]
    if not provider_key_configured(model.get("provider", "")):
        alternatives = {item["provider"] for item in model_catalog()
                        if provider_key_configured(item["provider"])}
        if not alternatives:
            return False, "Connect a model provider in Setup before chatting."
    try:
        from app.registry.runtime import require_model
        require_model(model["provider"], model["model"], tool_calling=False)
    except Exception:
        return False, "This agent's model is not currently approved and available in the model catalogue."
    return True, ""


def model_catalog():
    from app.registry.runtime import get_registry
    from app.registry.models import ModelRequirements
    labels = {
        "upstage/solar-mini4": ("Solar Mini 4", "Fast · low cost"),
        "cohere/command-a-plus": ("Command A+", "Balanced"),
        "openai/gpt-6-luna": ("GPT-6 Luna", "Fast"),
        "openai/gpt-6-luna-pro": ("GPT-6 Luna Pro", "Fast · stronger"),
        "openai/gpt-6-sol": ("GPT-6 Sol", "Strong"),
        "openai/gpt-6.1-sol": ("GPT-6.1 Sol", "Very strong"),
        "openai/gpt-6.1-sol-pro": ("GPT-6.1 Sol Pro", "Maximum reasoning"),
        "anthropic/claude-sonnet-5.5": ("Claude Sonnet 5.5", "Very strong"),
        "qwen/qwen3.8-max-prime": ("Qwen3.8 Max Prime", "Strong · fast"),
    }
    entries = get_registry().candidates(ModelRequirements(
        tool_calling=True, structured_output=True, allow_router=get_settings().allow_model_router,
        max_reservation_usd=Decimal("1.00"),
    ))
    return [{
        "provider": entry.provider, "model": entry.model,
        "label": labels.get(entry.model, (entry.model, "Approved"))[0],
        "tier": labels.get(entry.model, (entry.model, "Approved"))[1],
        "router": entry.is_router,
        "max_call_usd": str(entry.reservation()),
        "input_usd_per_million": str(entry.pricing.input_usd_per_million),
        "output_usd_per_million": str(entry.pricing.output_usd_per_million),
        "notes": entry.notes,
    } for entry in entries]


def validate_model_selection(provider, model, *, tool_calling=False, structured_output=False, budget=None):
    if not provider and not model:
        return
    if bool(provider) != bool(model):
        raise ValueError("Model provider and model must be selected together")
    from app.registry.runtime import require_model
    from app.telemetry.costs import BudgetBlocked
    try:
        entry = require_model(provider, model, tool_calling=tool_calling, structured_output=structured_output)
    except BudgetBlocked as error:
        raise ValueError(str(error)) from error
    if budget is not None and entry.reservation() > budget:
        raise ValueError("The selected model's maximum call reservation exceeds this operation's budget")


def operation_failure_message(error: Exception, kind: str) -> str:
    """Return a useful provider failure without exposing request credentials."""
    name = type(error).__name__
    detail = " ".join(str(error).split())[:240]
    lowered = (name + " " + detail).casefold()
    if "timeout" in lowered or "timed out" in lowered:
        settings = get_settings()
        seconds = (int(getattr(settings, "model_chat_timeout_seconds", 60))
                   if kind in {"chat", "agent_chat"}
                   else int(getattr(settings, "model_build_timeout_seconds", 150)))
        return (f"Model timeout after {seconds}s. The provider returned no reply. "
                "Retry with another approved named model.")
    if "rate" in lowered and "limit" in lowered:
        return "Provider rate limit reached. Wait briefly or select another named model."
    if "credit" in lowered or "balance" in lowered:
        return "The model provider rejected the call because the account has insufficient credit."
    if "api key" in lowered or "unauthorized" in lowered or "authentication" in lowered:
        return "The model provider rejected the API key. Reconnect it in Setup."
    if "connection" in lowered:
        return "The model provider could not be reached. Check the connection and retry with another model."
    return f"{name}: {detail or 'The operation failed before the provider returned a usable reply.'}"


def create_app(data_root: Path | None = None):
    store = ProjectStore(data_root or PROJECT_ROOT / "data")
    integrations = IntegrationStore(store.root)
    if store.root == (PROJECT_ROOT / "data").resolve():
        integrations.migrate_legacy_env(PROJECT_ROOT / ".env")
    integrations.load()
    obsidian = ObsidianBridge(store.root)
    token = secrets.token_urlsafe(32)

    @asynccontextmanager
    async def lifespan(app):
        store.recover_jobs()
        yield

    app = FastAPI(title="Research Atelier", version=VERSION, lifespan=lifespan)
    app.state.store = store
    app.state.integrations = integrations
    app.state.obsidian = obsidian
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_allowed_hosts())

    @app.middleware("http")
    async def same_origin(request: Request, call_next):
        origin = request.headers.get("origin")
        if origin:
            origin_host = urlsplit(origin).netloc.lower()
            request_host = request.headers.get("host", "").lower()
            if not origin_host or origin_host != request_host:
                return JSONResponse({"detail": "Origin is not allowed"}, status_code=403)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            if not secrets.compare_digest(request.headers.get("x-factory-token", ""), token):
                return JSONResponse({"detail": "Session expired; reload the page"}, status_code=403)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
        if request.url.path == "/" or request.url.path.startswith("/static/"):
            response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ValueError)
    async def invalid(request, error):
        return JSONResponse({"detail": str(error)[:500]}, status_code=400)

    @app.exception_handler(FileNotFoundError)
    async def missing(request, error):
        return JSONResponse({"detail": "Resource not found"}, status_code=404)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "research-agent-factory", "version": VERSION}

    @app.get("/api/session")
    def session():
        settings = get_settings()
        providers = integrations.status()
        models = model_catalog()
        for item in models:
            item["configured"] = providers.get(item["provider"], {}).get("configured", False)
        return {"token": token, "version": VERSION, "budget_usd": "1.00",
                "provider": settings.model_provider,
                "model": settings.openrouter_model if settings.model_provider == "openrouter" else settings.openai_model,
                "default_build_budget_usd": "1.00", "max_build_budget_usd": "1.00",
                "chat_timeout_seconds": settings.model_chat_timeout_seconds,
                "build_timeout_seconds": settings.model_build_timeout_seconds,
                "models": models, "providers": providers,
                "has_key": any(item["configured"] for item in models),
                "local_execution": "Generated tests execute locally, without an OS sandbox"}

    @app.get("/api/integrations")
    def integration_status():
        return {"providers": integrations.status(), "obsidian": obsidian.status()}

    @app.put("/api/integrations/providers/{provider}")
    def configure_provider(provider: str, data: ProviderKeyInput):
        if provider not in PROVIDERS:
            raise ValueError("Unknown model provider")
        result = integrations.set_key(provider, data.api_key, persist=data.persist)
        return {"provider": result}

    @app.delete("/api/integrations/providers/{provider}")
    def remove_provider(provider: str):
        if provider not in PROVIDERS:
            raise ValueError("Unknown model provider")
        return {"provider": integrations.remove_key(provider)}

    @app.put("/api/integrations/obsidian")
    def connect_obsidian(data: ObsidianInput):
        return {"obsidian": obsidian.connect(data.path)}

    @app.delete("/api/integrations/obsidian")
    def disconnect_obsidian():
        return {"obsidian": obsidian.disconnect()}

    @app.get("/api/harness")
    def harness():
        return describe_interface_harness()

    @app.get("/api/projects")
    def projects():
        return store.projects()

    @app.post("/api/projects", status_code=201)
    def create_project(data: ProjectInput):
        return store.create(data.name, data.question, data.domain)

    @app.delete("/api/projects/{project_id}")
    def delete_project(project_id: str):
        deleted = store.delete_project(project_id)
        return {"deleted": deleted["id"]}

    @app.get("/api/projects/{project_id}")
    def project(project_id: str):
        record = store.project(project_id)
        messages = store.messages(project_id)
        readiness = assess_research_brief(compile_research_brief(record["question"], messages))
        return {**record, "documents": store.documents(project_id),
                "jobs": store.jobs(project_id), "messages": messages,
                "research_status": readiness.to_dict(),
                "chunk_count": len(store.chunks(project_id))}

    @app.get("/api/projects/{project_id}/wiki")
    def wiki(project_id: str):
        store.project(project_id)
        return ProjectWiki(store.directory(project_id)).entries()

    @app.post("/api/projects/{project_id}/wiki", status_code=201)
    def add_wiki(project_id: str, data: WikiInput):
        store.project(project_id)
        if data.agent_id:
            item = store.job(data.agent_id)
            if item["project_id"] != project_id or item["kind"] != "build":
                raise ValueError("Agent does not belong to this project")
        return ProjectWiki(store.directory(project_id)).add(data.title, data.content, agent_id=data.agent_id)

    @app.post("/api/projects/{project_id}/obsidian/sync")
    def sync_obsidian(project_id: str):
        record = store.project(project_id)
        return obsidian.sync(record, store.directory(project_id))

    @app.get("/api/projects/{project_id}/wiki/export")
    def export_wiki(project_id: str):
        store.project(project_id)
        return Response(ProjectWiki(store.directory(project_id)).export_zip(), media_type="application/zip",
                        headers={"Content-Disposition": 'attachment; filename="research-wiki.zip"'})

    @app.post("/api/projects/{project_id}/documents")
    async def upload(project_id: str, file: UploadFile = File(...)):
        raw = await file.read(20_000_001)
        try:
            result = store.add_document(project_id, file.filename or "document.txt", raw)
            if not result.get("duplicate"):
                ProjectWiki(store.directory(project_id)).add("Source added: " + result["name"][:135],
                    "Document ID: `" + result["id"] + "`\n\nSHA-256: `" + result["sha256"] + "`", kind="source")
            return result
        finally:
            await file.close()

    @app.get("/api/projects/{project_id}/documents/{document_id}")
    def download(project_id: str, document_id: str):
        path, name = store.source(project_id, document_id)
        return FileResponse(path, filename=name, media_type="application/octet-stream")

    @app.post("/api/projects/{project_id}/search")
    def search(project_id: str, data: QueryInput):
        return {"strategy": "bm25", "hits": store.search(project_id, data.query, data.limit)}

    @app.get("/api/skills")
    def skills():
        return SkillLibrary().entries

    @app.post("/api/projects/{project_id}/evaluations")
    async def evaluate(project_id: str, job_id: str, file: UploadFile = File(...)):
        from app.schemas.results import ExperimentResults
        from app.planning.build_evaluation import archive_build_results
        from app.planning.result_store import load_evaluation
        job = store.job(job_id)
        if job["project_id"] != project_id or job["kind"] != "build" or job["status"] != "passed":
            raise ValueError("Select a completed build in this project")
        try:
            raw = await file.read(10_000_001)
            if len(raw) > 10_000_000:
                raise ValueError("Measurements exceed 10 MB")
            results = ExperimentResults.model_validate_json(raw)
        finally:
            await file.close()
        directory = archive_build_results(store.directory(project_id) / "builds", job["result"]["build_id"], results)
        ProjectWiki(store.directory(project_id)).add("Evaluation archived", "Archive: `" + directory.name +
            "`\n\nBuild: `" + job["result"]["build_id"] + "`", kind="evaluation", agent_id=job_id)
        return {"id": directory.name, "report": load_evaluation(directory)["report"]}

    @app.get("/api/projects/{project_id}/evaluations")
    def evaluations(project_id: str):
        from app.planning.result_store import load_evaluation
        store.project(project_id)
        root = store.directory(project_id) / "builds" / ".research_evaluations"
        reports = []
        if root.is_dir():
            for directory in sorted(root.iterdir(), reverse=True):
                if directory.is_symlink() or not directory.is_dir():
                    continue
                try:
                    loaded = load_evaluation(directory)
                    reports.append({"id": directory.name, "build_id": str(loaded["results"].source_build_id), "report": loaded["report"]})
                except (OSError, ValueError):
                    reports.append({"id": directory.name, "error": "Incomplete archive or invalid integrity"})
        return reports

    @app.get("/api/skills/{identifier}")
    def read_skill(identifier: str):
        return {"id": identifier, "content": SkillLibrary().read(identifier)}

    @app.put("/api/projects/{project_id}/skills")
    def save_skills(project_id: str, identifiers: list[str]):
        if len(identifiers) > 8 or len(set(identifiers)) != len(identifiers):
            raise ValueError("Choose up to eight distinct skills")
        library = SkillLibrary()
        for identifier in identifiers:
            library.read(identifier)
        store.set_skills(project_id, identifiers)
        ProjectWiki(store.directory(project_id)).add("Skill set updated",
            "Selected skills:\n" + ("\n".join("- `" + identifier + "`" for identifier in identifiers) or "- none"), kind="skill")
        return {"selected": identifiers}

    def dispatch(project_id, kind, tasks, operation):
        try:
            identifier = store.start_job(project_id, kind)
        except ValueError as error:
            active = next((job for job in store.jobs(project_id)
                           if job["status"] in {"queued", "running"}), None)
            if active:
                labels = {"build": "Research agent build", "chat": "Factory chat",
                          "agent_chat": "Agent reply", "skills": "Skill selection"}
                label = labels.get(active["kind"], active["kind"].replace("_", " ").title())
                raise HTTPException(status_code=409, detail=f"{label} is still {active['status']} (operation {active['id'][:8]}). Wait for it to finish, then retry.") from error
            raise
        def execute():
            store.update_job(identifier, "running", progress="Preparing operation")
            watchdog = None
            watchdog_lock = threading.Lock()
            settings = get_settings()
            stall_seconds = (
                int(getattr(settings, "model_chat_timeout_seconds", 60)) + 10
                if kind in {"chat", "agent_chat"}
                else int(getattr(settings, "model_build_timeout_seconds", 150)) + 30
            )

            def expire_operation():
                failure = (
                    f"Operation timed out after {stall_seconds}s without progress. "
                    "The project is unlocked; retry with another approved named model."
                )
                store.update_job_if_active(
                    identifier, "failed", error=failure,
                    progress="Timed out; the project is ready for another operation",
                )

            def arm_watchdog():
                nonlocal watchdog
                with watchdog_lock:
                    if watchdog is not None:
                        watchdog.cancel()
                    watchdog = threading.Timer(stall_seconds, expire_operation)
                    watchdog.daemon = True
                    watchdog.start()

            arm_watchdog()

            def report_progress(message):
                if store.update_job_if_active(identifier, "running", progress=str(message)[:300]):
                    arm_watchdog()
            try:
                result = operation(report_progress, identifier)
                status = result.get("status", "passed") if isinstance(result, dict) else "passed"
                completed = store.update_job_if_active(identifier, status, result=result)
                if completed and kind == "build":
                    clarification = build_clarification(result)
                    if clarification:
                        # A scientific intake gate is a conversation turn, not a
                        # broken agent. Surface it in the factory terminal so the
                        # next user answer becomes part of the compiled brief.
                        store.message(project_id, "assistant", clarification)
                    ProjectWiki(store.directory(project_id)).add("Agent build " + status,
                        "Job: `" + identifier + "`\n\nBuild: `" + str(result.get("build_id", "unknown")) +
                        "`\n\nStatus: **" + status + "**", kind="build", agent_id=identifier)
                if completed and kind == "skills":
                    ProjectWiki(store.directory(project_id)).add("Skills proposed",
                        "Decision backend: `" + result.get("backend", "unknown") + "`\n\n" +
                        "\n".join("- `" + selected + "`" for selected in result.get("selected", [])), kind="skill")
            except Exception as error:
                failure = operation_failure_message(error, kind)
                store.update_job_if_active(identifier, "failed", error=failure, progress=failure)
            finally:
                with watchdog_lock:
                    if watchdog is not None:
                        watchdog.cancel()
        tasks.add_task(execute)
        return {"job_id": identifier, "status": "queued"}

    @app.post("/api/projects/{project_id}/skills/select")
    def select_skills(project_id: str, data: BuildInput, background_tasks: BackgroundTasks):
        return dispatch(project_id, "skills", background_tasks,
                        lambda progress, _job_id: select_project_skills(store, project_id, data.backend, progress=progress))

    @app.post("/api/projects/{project_id}/build")
    def build(project_id: str, data: BuildInput, background_tasks: BackgroundTasks):
        if data.mode not in {"demo", "live"} or data.backend not in {"configured", "jev"}:
            raise ValueError("Invalid build mode or decision backend")
        if data.mode == "live":
            record = store.project(project_id)
            brief = compile_research_brief(record["question"], store.messages(project_id), data.question)
            readiness = assess_research_brief(brief)
            if not readiness.ready:
                raise ValueError("RESEARCH_BRIEF_INCOMPLETE: " + readiness.clarification)
            selected_provider = data.model_provider or get_settings().model_provider
            if not provider_key_configured(selected_provider):
                raise ValueError("Connect the selected model provider in Setup. No build was started.")
            validate_model_selection(data.model_provider, data.model, tool_calling=True,
                                     structured_output=True, budget=data.budget_usd)
        else:
            brief = data.question
        return dispatch(project_id, "build", background_tasks,
                        lambda progress, _job_id: run_build(store, project_id, mode=data.mode, backend=data.backend,
                                          repairs=data.repairs, budget_usd=data.budget_usd,
                                          question=brief, progress=progress,
                                          model_provider=data.model_provider, model=data.model))

    @app.get("/api/projects/{project_id}/agents/{job_id}")
    def agent_details(project_id: str, job_id: str):
        item = store.job(job_id)
        if item["project_id"] != project_id or item["kind"] != "build":
            raise FileNotFoundError()
        build = item.get("result") or {}
        build_id = build.get("build_id")
        if not build_id:
            return {"job": item, "spec": None, "skills": [], "mcp": None, "rag": None,
                    "costs": None, "code_files": [], "chat_available": False,
                    "chat_unavailable_reason": "This build did not produce a research agent."}
        from uuid import UUID
        directory = store.directory(project_id) / "builds" / ".factory_runs" / str(UUID(build_id))
        if not directory.is_dir() or directory.is_symlink():
            raise FileNotFoundError()
        def read_json(name):
            path = directory / name
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 2_000_000:
                return None
            return json.loads(path.read_text(encoding="utf-8"))
        spec = read_json("agent_spec.json")
        chat_available, chat_reason = agent_chat_readiness(spec)
        build_skills = (read_json("skills_selection.json") or {}).get("selected", [])
        chat_skills = (SkillLibrary().select(
            ((spec or {}).get("objective") or store.project(project_id)["question"]), max_skills=5,
        )["selected"] if spec else [])
        mcp_selection = read_json("mcp_selection.json") or {"tools": []}
        persisted_tools = [f"{item['server']}/{item['tool']}" for item in mcp_selection.get("tools", [])
                           if isinstance(item, dict) and item.get("server") and item.get("tool")]
        standard_tools = ["factory-bm25/search", "factory-bm25/read_chunk", "factory-web/web_search"]
        chat_tools = list(dict.fromkeys([*persisted_tools, *standard_tools]))
        return {"job": item, "spec": spec, "chat_available": chat_available,
                "chat_unavailable_reason": chat_reason,
                "protocol": read_json("research_protocol.json"),
                "research_library": read_json("research_library.json"),
                "skills": build_skills, "chat_skills": chat_skills,
                "mcp": mcp_selection, "chat_tools": chat_tools,
                "runtime_tools_inherited": not bool(persisted_tools),
                "rag": read_json("retrieval_snapshot.json"),
                "costs": read_json("cost_summary.json"), "messages": store.agent_messages(project_id, job_id),
                "runtime": read_json("runtime_config.json"),
                "response_runs": [job for job in store.jobs(project_id)
                                  if job["kind"] == "agent_chat" and
                                  (job.get("result") or {}).get("agent_id") == job_id][:10],
                "code_files": files(project_id, job_id) if build.get("workspace") else []}

    @app.delete("/api/projects/{project_id}/jobs/{job_id}")
    def delete_job(project_id: str, job_id: str):
        item = store.job(job_id)
        if item["project_id"] != project_id:
            raise FileNotFoundError()
        if item["kind"] == "build":
            ProjectWiki(store.directory(project_id)).delete_agent_entries(job_id)
        store.delete_job(project_id, job_id)
        return {"deleted": job_id}

    @app.get("/api/projects/{project_id}/agents/{job_id}/messages")
    def agent_messages(project_id: str, job_id: str):
        return store.agent_messages(project_id, job_id)

    @app.post("/api/projects/{project_id}/agents/{job_id}/chat")
    def ask_agent(project_id: str, job_id: str, data: AgentChatInput, background_tasks: BackgroundTasks):
        item = store.job(job_id)
        if item["project_id"] != project_id or item["kind"] != "build" or item["status"] != "passed":
            raise ValueError("Open a completed agent from this project before starting its chat")
        details = agent_details(project_id, job_id)
        if not details["chat_available"]:
            raise ValueError(details["chat_unavailable_reason"])
        validate_model_selection(data.model_provider, data.model, budget=Decimal("1.00"))
        selected_provider = data.model_provider or (details.get("spec") or {}).get("model", {}).get("provider")
        if not selected_provider or not provider_key_configured(selected_provider):
            raise ValueError("Connect the selected model provider in Setup.")
        return dispatch(project_id, "agent_chat", background_tasks,
                        lambda progress, _job_id: agent_chat(store, project_id, job_id, data.query, progress=progress,
                                                    model_provider=data.model_provider, model=data.model))

    @app.post("/api/projects/{project_id}/chat")
    def ask(project_id: str, data: QueryInput, background_tasks: BackgroundTasks):
        if data.mode not in {"sources", "live"}:
            raise ValueError("Invalid answer mode")
        if data.mode == "live":
            validate_model_selection(data.model_provider, data.model, budget=Decimal("1.00"))
            selected_provider = data.model_provider or get_settings().model_provider
            if not provider_key_configured(selected_provider):
                raise ValueError("Connect the selected model provider in Setup.")
        return dispatch(project_id, "chat", background_tasks,
                        lambda progress, chat_job_id: chat(store, project_id, data.query, mode=data.mode, progress=progress,
                                              model_provider=data.model_provider, model=data.model, agent_id=chat_job_id))

    @app.get("/api/jobs/{identifier}")
    def job(identifier: str):
        result = store.job(identifier)
        root = store.directory(result["project_id"]) / "builds" / ".factory_runs"
        if result["kind"] == "build" and root.exists():
            directories = sorted(root.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
            build_id = (result.get("result") or {}).get("build_id")
            if build_id:
                directories = [p for p in directories if p.name == build_id]
            elif result["status"] not in {"queued", "running"}:
                directories = []
            if directories:
                event_path = directories[0] / "events.jsonl"
                if event_path.is_file():
                    events = []
                    for line in event_path.read_text(encoding="utf-8").splitlines()[-60:]:
                        try:
                            events.append(json.loads(line))
                        except ValueError:
                            pass
                    result["events"] = events
        return result

    @app.get("/api/projects/{project_id}/files")
    def files(project_id: str, job_id: str):
        item = store.job(job_id)
        if item["project_id"] != project_id or not item["result"] or not item["result"].get("workspace"):
            raise FileNotFoundError()
        workspace = Path(item["result"]["workspace"]).resolve(strict=True)
        if not workspace.is_relative_to(store.directory(project_id)):
            raise ValueError("Workspace fora do projeto")
        return [{"path": path.relative_to(workspace).as_posix(), "size": path.stat().st_size}
                for path in workspace.rglob("*") if path.is_file() and not path.is_symlink()
                and path.resolve().is_relative_to(workspace) and path.suffix in {".py", ".md", ".json", ".txt"}
                and "__pycache__" not in path.parts][:300]

    @app.get("/api/projects/{project_id}/file")
    def read_file(project_id: str, job_id: str, path: str):
        from app.tools.filesystem import resolve_workspace_path
        allowed = {item["path"] for item in files(project_id, job_id)}
        if path not in allowed:
            raise FileNotFoundError()
        workspace = Path(store.job(job_id)["result"]["workspace"])
        target = resolve_workspace_path(workspace, path)
        if target.stat().st_size > 1_000_000:
            raise ValueError("File is too large to preview")
        return {"path": path, "content": target.read_text(encoding="utf-8")}

    @app.post("/api/projects/{project_id}/web-search")
    def web_search(project_id: str, data: QueryInput):
        from app.research_web import search_papers
        store.project(project_id)
        try:
            return {"results": search_papers(data.query, data.limit, data.provider)}
        except ValueError:
            raise
        except Exception:
            raise HTTPException(502, "The public search provider did not respond; try again") from None

    @app.get("/api/mcps")
    def mcps():
        return {"local": [{"id": "factory-bm25", "status": "available", "description": "Search and read documents in a bound project"},
                           {"id": "factory-web", "status": "available", "description": "Search arXiv, Crossref, OpenAlex and Semantic Scholar"}],
                "external": [entry for entry in SkillLibrary().entries if entry["kind"] == "mcp"]}

    static = Path(__file__).with_name("static")
    app.mount("/static", StaticFiles(directory=static), name="static")

    @app.get("/")
    def home():
        return FileResponse(static / "index.html")

    return app
