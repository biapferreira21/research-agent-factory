"""Leitura local de builds; não executa agentes, testes ou modelos."""
import json
from pathlib import Path
from uuid import UUID

from app.planning.result_store import load_evaluation
from app.telemetry.schemas import BuildEvent


def build_report(root: Path, build_id: str, *, include_evaluations: bool = True) -> dict:
    identifier = str(UUID(build_id))
    root = root.resolve(strict=True)
    directory = (root / ".factory_runs" / identifier).resolve(strict=True)
    if not directory.is_relative_to(root):
        raise ValueError("Build fora da raiz da factory.")
    issues = []

    def records(name):
        path = directory / name
        if not path.exists():
            return []
        if path.is_symlink() or path.resolve().parent != directory:
            raise ValueError("Log fora da pasta do build.")
        with path.open("rb") as handle:
            raw = handle.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError("Log excede 10 MB.")
        values = []
        for number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if not isinstance(value, dict):
                    raise ValueError("object expected")
                values.append(value)
            except ValueError:
                issues.append(f"{name}: linha {number} inválida")
        return values

    events = []
    for value in records("events.jsonl"):
        try:
            event = BuildEvent.model_validate(value)
            if event.build_id != identifier:
                raise ValueError("wrong build")
            events.append(event)
        except ValueError:
            issues.append("Evento inválido ou associado a outro build")
    last = events[-1] if events else None
    status = last.status if last and last.stage == "finished" else "incomplete"
    acceptance = records("acceptance.jsonl")
    if issues:
        status = "unreliable_logs"
    evaluations = []
    archive_root = root / ".research_evaluations"
    if include_evaluations and archive_root.exists():
        if archive_root.is_symlink() or not archive_root.resolve().is_relative_to(root):
            raise ValueError("Arquivo fora da raiz da factory.")
        for archive in sorted(archive_root.iterdir()):
            if not archive.is_dir() or archive.is_symlink():
                continue
            try:
                loaded = load_evaluation(archive)
                if str(loaded["results"].source_build_id) == identifier:
                    evaluations.append({"archive_id": archive.name, "origin": loaded["results"].origin,
                                        "status": loaded["report"]["status"],
                                        "criteria_met": loaded["report"]["criteria_met"]})
            except (OSError, ValueError, TypeError, AttributeError):
                # Não sabemos a que build pertence um arquivo cuja integridade falhou.
                issues.append(f"Arquivo não verificável: {archive.name}")
    return {"build_id": identifier, "status": status,
            "last_stage": last.stage.value if last else None,
            "costs_at_last_event": last.costs.model_dump(mode="json") if last else None,
            "repair_attempts_started": sum(event.stage == "repairing" and event.status == "started" for event in events),
            "acceptance_records": len(acceptance),
            "last_acceptance": acceptance[-1] if acceptance else None,
            "research_evaluations": evaluations, "issues": issues}


def list_builds(root: Path, *, limit: int = 10, offset: int = 0) -> dict:
    """Paginar por mtime da pasta do build, sem varrer avaliações científicas."""
    if type(limit) is not int or not 1 <= limit <= 100 or type(offset) is not int or offset < 0:
        raise ValueError("limit deve estar entre 1 e 100; offset deve ser não negativo.")
    root = root.resolve(strict=True)
    runs = root / ".factory_runs"
    if not runs.exists():
        return {"builds": [], "total": 0, "next_offset": None}
    if runs.is_symlink() or not runs.resolve().is_relative_to(root):
        raise ValueError("Pasta de builds fora da raiz.")
    entries = []
    for path in runs.iterdir():
        if not path.is_dir() or path.is_symlink() or not path.resolve().is_relative_to(runs.resolve()):
            continue
        try:
            if str(UUID(path.name)) != path.name:
                continue
        except ValueError:
            continue
        entries.append((path.stat().st_mtime_ns, path.name))
    entries.sort(reverse=True)
    builds = []
    for _, identifier in entries[offset:offset + limit]:
        try:
            report = build_report(root, identifier, include_evaluations=False)
            builds.append({key: report[key] for key in (
                "build_id", "status", "last_stage", "repair_attempts_started", "issues")})
        except (OSError, ValueError):
            builds.append({"build_id": identifier, "status": "unreadable",
                           "last_stage": None, "repair_attempts_started": None,
                           "issues": ["Não foi possível ler os logs deste build."]})
    end = offset + limit
    return {"builds": builds, "total": len(entries),
            "next_offset": end if end < len(entries) else None}
