"""Demonstração local, sem modelos, embeddings ou rede."""
from pathlib import Path

from app.retrieval.local import LocalIndex, Source


def main():
    root = Path(__file__).resolve().parent / "examples" / "knowledge"
    index = LocalIndex(root, [
        Source(path="global.md", scope="global"),
        Source(path="statistics.md", scope="domain", domain="statistics"),
        Source(path="project_a.md", scope="project", project="a"),
    ])
    for hit in index.search("baseline erro", domain="statistics", project="a"):
        print(hit.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
