"""Arquivo local de avaliações. Manifesto escrito por último marca conclusão."""
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from app.planning.result_evaluation import evaluate_results
from app.schemas.research import ResearchProtocol
from app.schemas.results import ExperimentResults


FILES = ("protocol.json", "results.json", "evaluation.json")


def save_evaluation(root: Path, protocol: ResearchProtocol, results: ExperimentResults) -> Path:
    protocol = ResearchProtocol.model_validate(protocol.model_dump())
    results = ExperimentResults.model_validate(results.model_dump())
    report = evaluate_results(protocol, results)
    # Guardar também avaliações inválidas para diagnóstico, sem as aprovar.
    contents = (protocol.model_dump_json(indent=2), results.model_dump_json(indent=2),
                json.dumps(report, ensure_ascii=False, indent=2))
    if any(len(content.encode("utf-8")) > 10_000_000 for content in contents):
        raise ValueError("Artefacto excede 10 MB.")
    directory = root.resolve() / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    hashes = {}
    for name, content in zip(FILES, contents):
        raw = content.encode("utf-8")
        with (directory / name).open("xb") as handle:
            handle.write(raw)
        hashes[name] = hashlib.sha256(raw).hexdigest()
    manifest = {"format_version": 1, "evaluator_version": "relative_mean_v1", "sha256": hashes}
    with (directory / "manifest.json").open("x", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
    return directory


def load_evaluation(directory: Path) -> dict:
    directory = directory.resolve(strict=True)
    # Os nomes são constantes; nunca usar caminhos fornecidos pelo manifesto.
    def read(name):
        path = directory / name
        if path.is_symlink() or path.resolve(strict=True).parent != directory:
            raise ValueError("Artefacto fora da pasta de avaliação.")
        with path.open("rb") as handle:
            raw = handle.read(10_000_001)
        if len(raw) > 10_000_000:
            raise ValueError("Artefacto excede 10 MB.")
        return raw

    manifest = json.loads(read("manifest.json"))
    if (manifest.get("format_version") != 1 or
            manifest.get("evaluator_version") != "relative_mean_v1" or
            set(manifest.get("sha256", {})) != set(FILES)):
        raise ValueError("Manifesto ou versão não suportados.")
    contents = {}
    for name in FILES:
        raw = read(name)
        if hashlib.sha256(raw).hexdigest() != manifest["sha256"][name]:
            raise ValueError(f"Integridade inválida: {name}")
        contents[name] = raw
    protocol = ResearchProtocol.model_validate_json(contents["protocol.json"])
    results = ExperimentResults.model_validate_json(contents["results.json"])
    saved_report = json.loads(contents["evaluation.json"])
    # Recalcular deteta relatórios incoerentes mesmo com hashes atualizados.
    recomputed = json.loads(json.dumps(evaluate_results(protocol, results)))
    if saved_report != recomputed:
        raise ValueError("Relatório diverge da avaliação recalculada.")
    return {"protocol": protocol, "results": results, "report": saved_report}
