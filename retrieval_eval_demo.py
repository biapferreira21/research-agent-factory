"""Suite didática offline; cada execução guarda um relatório novo."""
import json
from pathlib import Path
from uuid import uuid4

from app.retrieval.evaluation import RetrievalCase, evaluate
from app.retrieval.local import LocalIndex, Source


def main():
    root = Path(__file__).resolve().parent
    knowledge = root / "examples" / "knowledge"
    index = LocalIndex(knowledge, [
        Source(path="global.md", scope="global"),
        Source(path="statistics.md", scope="domain", domain="statistics"),
        Source(path="project_a.md", scope="project", project="a"),
    ])
    cases = [RetrievalCase.model_validate(item) for item in
             json.loads((knowledge / "retrieval_cases.json").read_text(encoding="utf-8"))]
    report = evaluate(index, cases)
    directory = root / "generated_agents" / ".retrieval_evals" / str(uuid4())
    directory.mkdir(parents=True, exist_ok=False)
    path = directory / "report.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Casos aprovados: {report['passed_count']}/{report['case_count']}")
    print(f"Relatorio: {path}")
    return 0 if report["passed_count"] == report["case_count"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
