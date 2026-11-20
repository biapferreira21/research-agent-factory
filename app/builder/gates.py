import ast
from pathlib import Path


def python_syntax_gate(workspace: Path) -> list[str]:
    errors: list[str] = []
    for path in workspace.rglob("*.py"):
        try:
            source = path.read_text(encoding="utf-8")

            ast.parse(
                source,
                filename=str(path),
            )

        except SyntaxError as exc:
            relative_path = path.relative_to(workspace)

            errors.append(
                f"Syntax error in {relative_path}: {exc}"
            )

    return errors

def required_structure_gate(workspace: Path) -> list[str]:
    errors: list[str] = []

    spec_path = workspace / "agent_spec.json"

    if not spec_path.is_file():
        errors.append("Missing required file: agent_spec.json")

    python_files = [
        path
        for path in workspace.rglob("*.py")
        if "tests" not in path.parts
    ]

    if not python_files:
        errors.append(
            "Generated project has no production Python files"
        )

    tests_dir = workspace / "tests"

    if not tests_dir.is_dir():
        errors.append("Missing required directory: tests")
    else:
        test_files = list(
            tests_dir.rglob("test_*.py")
        )

        if not test_files:
            errors.append(
                "Generated project has no pytest test files"
            )

    return errors

def run_all_gates(workspace: Path) -> list[str]:
    errors: list[str] = []

    errors.extend(
        required_structure_gate(workspace)
    )

    errors.extend(
        python_syntax_gate(workspace)
    )

    return errors

