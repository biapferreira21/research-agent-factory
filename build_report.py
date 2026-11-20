"""Consultar um build pelo UUID, sem executar trabalho adicional."""
import argparse
import json
from pathlib import Path

from app.config import get_workspace_root
from app.telemetry.report import build_report, list_builds


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("build_id", nargs="?", help="UUID devolvido pelo harness")
    parser.add_argument("--list", action="store_true", help="Listar builds recentes")
    parser.add_argument("--limit", type=int, default=10, help="Builds por página (1 a 100)")
    parser.add_argument("--offset", type=int, default=0, help="Número de builds a saltar")
    parser.add_argument("--root", type=Path, default=None, help="Raiz que contém .factory_runs")
    args = parser.parse_args()
    if args.list == bool(args.build_id):
        parser.error("Escolhe um UUID ou --list.")
    if not args.list and (args.limit != 10 or args.offset != 0):
        parser.error("--limit e --offset aplicam-se apenas a --list.")
    try:
        root = args.root if args.root is not None else get_workspace_root()
        report = list_builds(root, limit=args.limit, offset=args.offset) if args.list else build_report(root, args.build_id)
    except (OSError, ValueError):
        parser.exit(2, "Não foi possível ler o build: verifica o UUID, a raiz e os ficheiros.\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
