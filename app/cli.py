"""Entrada única para a aplicação, builds, bibliotecas e avaliações."""
import argparse
import json
from pathlib import Path
import sys


def output(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="agent-factory", description="Research Atelier — local agent factory")
    sub = parser.add_subparsers(dest="command", required=True)
    serve = sub.add_parser("serve", help="Abrir aplicação local HTML/JavaScript")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=8765)
    serve.add_argument("--data", type=Path, default=Path("data"))
    sub.add_parser("doctor", help="Diagnóstico local sem expor credenciais")
    demo = sub.add_parser("demo", help="Pipeline offline com pytest real")
    demo.add_argument("--root", type=Path, default=Path("generated_agents"))
    build = sub.add_parser("build", help="Construir com modelos reais")
    build.add_argument("requirement")
    build.add_argument("--research", action="store_true")
    build.add_argument("--config", type=Path)
    listing = sub.add_parser("list", help="Listar builds guardados")
    listing.add_argument("--root", type=Path, default=Path("generated_agents"))
    listing.add_argument("--limit", type=int, default=10)
    show = sub.add_parser("show", help="Inspecionar um build")
    show.add_argument("build_id")
    show.add_argument("--root", type=Path, default=Path("generated_agents"))
    skills = sub.add_parser("skills", help="Listar biblioteca ou pesquisar skills")
    skills.add_argument("--query")
    evaluate = sub.add_parser("evaluate", help="Avaliar medições de um build científico")
    evaluate.add_argument("build_id")
    evaluate.add_argument("results", type=Path)
    evaluate.add_argument("--root", type=Path, default=Path("generated_agents"))
    args = parser.parse_args(argv)
    try:
        if args.command == "serve":
            import uvicorn
            from app.web import create_app
            if not args.host.strip():
                raise ValueError("Host não pode estar vazio")
            if not 1024 <= args.port <= 65535:
                raise ValueError("Porta deve estar entre 1024 e 65535")
            uvicorn.run(create_app(args.data), host=args.host, port=args.port, log_level="info")
        elif args.command == "doctor":
            from app.config import get_settings, get_model_registry_path
            from app.integrations import IntegrationStore
            from app.registry.models import ModelRegistry
            from app.registry.skills import SkillLibrary
            IntegrationStore(Path("data")).load()
            settings = get_settings()
            registry = ModelRegistry.load(get_model_registry_path())
            output({"python": sys.version.split()[0], "provider": settings.model_provider,
                    "model": settings.openrouter_model if settings.model_provider == "openrouter" else settings.openai_model,
                    "key_configured": bool(settings.openrouter_api_key if settings.model_provider == "openrouter" else settings.openai_api_key),
                    "budget_usd": str(settings.build_budget_usd), "skills": len(SkillLibrary().entries),
                    "model_registry_valid": True, "python_314_warning": sys.version_info >= (3,14),
                    "local_mcps": ["factory-bm25", "factory-web"], "network_tested": False})
        elif args.command == "demo":
            from app.demo import run
            result = run(args.root)
            output(result)
            return 0 if result["build"]["status"] == "passed" else 1
        elif args.command == "build":
            from app.builder.harness import BuilderHarness
            from app.run_config import load_run_config, resolve
            from app.project_runtime import decision_service
            from app.registry.skills import SkillLibrary
            from app.tools.acceptance import PythonAcceptance
            config, base = load_run_config(args.config)
            harness = BuilderHarness(root=resolve(base, config.workspace_root), budget_usd=config.budget_usd,
                                     max_repair_attempts=config.max_repair_attempts,
                                     decision_service=decision_service(config.decision_backend),
                                     retrieval=config.knowledge.create(base) if config.knowledge else None,
                                     retrieval_cases=tuple(config.knowledge.cases) if config.knowledge and config.knowledge.cases else None,
                                     skill_library=SkillLibrary(), select_skills=True,
                                     acceptance_validator=PythonAcceptance(resolve(base, config.acceptance.script),
                                         timeout_seconds=config.acceptance.timeout_seconds) if config.acceptance else None)
            result = harness.build_research(args.requirement) if args.research else harness.build(args.requirement)
            output(result.to_dict())
            return 0 if result.status == "passed" else 1
        elif args.command in {"list", "show"}:
            from app.telemetry.report import list_builds, build_report
            output(list_builds(args.root, limit=args.limit) if args.command == "list" else build_report(args.root, args.build_id))
        elif args.command == "skills":
            from app.registry.skills import SkillLibrary
            library = SkillLibrary()
            output(library.candidates(args.query) if args.query else library.entries)
        elif args.command == "evaluate":
            from app.planning.build_evaluation import archive_build_results
            from app.planning.result_store import load_evaluation
            from app.schemas.results import ExperimentResults
            results = ExperimentResults.model_validate_json(args.results.read_text(encoding="utf-8"))
            path = archive_build_results(args.root, args.build_id, results)
            report = load_evaluation(path)["report"]
            output({"archive": str(path), "report": report})
            return 1 if report["status"] == "invalid_results" or report["criteria_met"] is False else 0
        return 0
    except (ValueError, OSError) as error:
        print(f"Operação não concluída ({type(error).__name__}). Verifica os argumentos e a configuração.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
