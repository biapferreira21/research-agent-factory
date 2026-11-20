"""Execução local de pytest. Não constitui uma sandbox para código gerado."""

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from langchain.tools import tool

from app.tools.filesystem import safe_path


@dataclass(frozen=True)
class PytestResult:
    exit_code: int | None
    output: str
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def as_text(self) -> str:
        # O código de saída nunca é removido pelo truncamento do log.
        return f"exit_code={self.exit_code}\n{self.output}"


def execute_pytest(workspace: Path) -> PytestResult:
    workspace = workspace.resolve()
    if not workspace.is_dir():
        raise ValueError(f"Test workspace does not exist: {workspace}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "."],
            cwd=workspace,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=120,
        )
    except subprocess.TimeoutExpired:
        return PytestResult(None, "Pytest execution timed out.", timed_out=True)
    output = f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    return PytestResult(result.returncode, output[-20000:])


@tool
def run_pytest(project_path: str) -> str:
    """Run pytest on a project inside the configured workspace root."""
    return execute_pytest(safe_path(project_path)).as_text()
