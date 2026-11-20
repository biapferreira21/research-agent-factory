from pathlib import Path, PureWindowsPath

from langchain.tools import tool

from app.config import get_workspace_root

def normalize_windows_path(path: Path) -> Path:
    value = str(path)

    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]

    return Path(value)



WORKSPACE_ROOT = get_workspace_root()
PROTECTED_CONTRACTS = frozenset({
    "agent_spec.json", "capability_spec.json", "mcp_selection.json", "mcp_configuration.json",
    "research_request.json", "research_question.json", "research_protocol.json",
    "evaluation_plan.json", "runtime_config.json",
})

def resolve_workspace_path(workspace: Path, relative_path: str) -> Path:
    """Resolver antes de verificar impede escapes por '..' e symlinks existentes."""
    windows_path = PureWindowsPath(relative_path)
    if Path(relative_path).is_absolute() or windows_path.drive or windows_path.root:
        raise ValueError("Use a relative path inside the workspace.")
    if ":" in relative_path:
        raise ValueError("Alternate data streams are not allowed.")
    if any(part not in (".", "..") and part.endswith((".", " ")) for part in windows_path.parts):
        raise ValueError("Trailing dots and spaces are not allowed in path components.")
    root = normalize_windows_path(
        workspace.resolve()
    )

    target = normalize_windows_path(
        (root / relative_path).resolve()
    )

    try:
        target.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"Path {relative_path} is outside the workspace root"
        ) from exc

    return target


def safe_path(relative_path: str) -> Path:
    # Compatibilidade com demos das ferramentas; o builder usa a factory abaixo.
    return resolve_workspace_path(WORKSPACE_ROOT, relative_path)


def create_filesystem_tools(workspace: Path):
    """Closures guardam a raiz de cada build sem alterar estado global."""
    root = normalize_windows_path(workspace.resolve())
    protected = {root / name for name in PROTECTED_CONTRACTS}

    @tool
    def write_file(path: str, content: str) -> str:
        """Write a file relative to this build. Approved JSON contracts are read-only."""
        target = resolve_workspace_path(root, path)
        if target in protected:
            raise ValueError(f"{target.name} is read-only.")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote: {target.relative_to(root)}"

    @tool
    def read_file(path: str) -> str:
        """Read a file relative to this build."""
        return resolve_workspace_path(root, path).read_text(encoding="utf-8")

    @tool
    def list_files(path: str = ".") -> str:
        """List files inside this build, using relative paths."""
        base = resolve_workspace_path(root, path)
        files = []
        for candidate in base.rglob("*"):
            if candidate.is_file():
                relative = candidate.relative_to(root).as_posix()
                resolve_workspace_path(root, relative)
                files.append(relative)
        return "\n".join(sorted(files))

    return [list_files, read_file, write_file]


@tool
def write_file(path: str, content: str) -> str:
    """
    Write content to a file at the given path.
    """
    target = safe_path(path)

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    target.write_text(
        content,
        encoding="utf-8",
    )

    return f"Wrote: {target.relative_to(WORKSPACE_ROOT)}"


@tool
def read_file(path: str) -> str:
    """
    Read content from a file at the given path.
    """
    target = safe_path(path)

    return target.read_text(
        encoding="utf-8",
    )


@tool
def list_files(path: str) -> str:
    """
    List all files in the given directory path.
    """
    base = safe_path(path)

    files = [
        str(p.relative_to(WORKSPACE_ROOT))
        for p in base.rglob("*")
        if p.is_file()
    ]

    return "\n".join(files)


