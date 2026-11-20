"""Associar medições a um build científico concluído, sem executar código gerado."""
import json
from pathlib import Path
from uuid import UUID

from app.planning.research_validation import protocol_digest
from app.planning.result_store import save_evaluation
from app.schemas.agent import AgentSpec
from app.schemas.research import ResearchProtocol
from app.schemas.results import ExperimentResults


def archive_build_results(factory_root: Path, build_id: str, results: ExperimentResults) -> Path:
    identifier = UUID(build_id)
    root = factory_root.resolve(strict=True)
    directory = (root / ".factory_runs" / str(identifier)).resolve(strict=True)
    if not directory.is_relative_to(root):
        raise ValueError("Build fora da pasta da factory.")

    def read(name):
        path = directory / name
        if path.is_symlink() or path.resolve(strict=True).parent != directory:
            raise ValueError("Contrato fora da pasta do build.")
        with path.open("rb") as handle:
            data = handle.read(10_000_001)
        if len(data) > 10_000_000:
            raise ValueError("Contrato excede 10 MB.")
        return data.decode("utf-8")

    events = [json.loads(line) for line in read("events.jsonl").splitlines() if line.strip()]
    if (not events or events[-1].get("stage") != "finished" or
            events[-1].get("status") != "passed" or
            any(event.get("build_id") != str(identifier) for event in events)):
        raise ValueError("É necessário um build concluído com sucesso.")
    protocol = ResearchProtocol.model_validate_json(read("research_protocol.json"))
    spec = AgentSpec.model_validate_json(read("agent_spec.json"))
    digest = protocol_digest(protocol)
    if spec.research_protocol_sha256 != digest:
        raise ValueError("AgentSpec e protocolo não correspondem.")
    results = ExperimentResults.model_validate(results.model_dump())
    if results.protocol_sha256 != digest:
        raise ValueError("As medições referem outro protocolo.")
    if results.source_build_id not in (None, identifier):
        raise ValueError("As medições já estão associadas a outro build.")
    linked = results.model_copy(update={"source_build_id": identifier})
    # Fora do workspace do builder; não altera contratos nem estado do build.
    archive_root = (root / ".research_evaluations").resolve()
    if not archive_root.is_relative_to(root):
        raise ValueError("Arquivo fora da pasta da factory.")
    return save_evaluation(archive_root, protocol, linked)
