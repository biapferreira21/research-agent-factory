"""Fail a release audit if local credentials or private runtime data are bundled."""
from __future__ import annotations

import argparse
import io
import json
from pathlib import Path
from zipfile import ZipFile


ROOT = Path(__file__).resolve().parents[1]
SECRET_NAMES = {"OPENAI_API_KEY", "OPENROUTER_API_KEY"}
SKIP_PARTS = {".git", ".venv", ".test_tmp", ".test-tmp", "dist", "build", "__pycache__"}


def skipped(relative: Path) -> bool:
    return any(part in SKIP_PARTS or part.startswith((".pytest-", "testtmp-"))
               for part in relative.parts)


def local_secrets() -> list[bytes]:
    values: list[bytes] = []
    for path in (ROOT / ".env", ROOT / "data" / "credentials.env"):
        if not path.is_file() or path.is_symlink():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line or line.lstrip().startswith("#"):
                continue
            name, value = line.split("=", 1)
            value = value.strip().strip("'\"")
            if name.strip() in SECRET_NAMES and len(value) >= 16:
                values.append(value.encode())
    return list(dict.fromkeys(values))


def source_leaks(secrets: list[bytes]) -> list[str]:
    allowed = {ROOT / ".env", ROOT / "data" / "credentials.env"}
    leaks = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.is_symlink() or path in allowed:
            continue
        relative = path.relative_to(ROOT)
        if skipped(relative) or path.stat().st_size > 20_000_000:
            continue
        try:
            content = path.read_bytes()
        except OSError:
            continue
        if any(secret in content for secret in secrets):
            leaks.append(relative.as_posix())
    return leaks


def wheel_audit(path: Path, secrets: list[bytes]) -> tuple[list[str], list[str], int]:
    forbidden, leaks = [], []
    with ZipFile(path) as archive:
        names = archive.namelist()
        for name in names:
            parts = Path(name).parts
            lowered = name.casefold()
            if (any(part in {"data", "generated_agents"} for part in parts)
                    or any(part in {".env", "credentials.env", "local_settings.json"} for part in parts)
                    or lowered.endswith((".sqlite3", ".log"))):
                forbidden.append(name)
            if secrets and any(secret in archive.read(name) for secret in secrets):
                leaks.append(name)
        skill_files = sum(name.startswith("skills/imported/") and not name.endswith("/") for name in names)
    return forbidden, leaks, skill_files


def bundle_audit(path: Path, secrets: list[bytes]) -> tuple[list[str], list[str], list[str]]:
    forbidden, leaks = [], []
    required = {"README.txt", "Install Agent Factory.cmd", "Start Agent Factory.cmd",
                "install.ps1", "start.ps1", "SDK.md", "SECURITY.md", "SHA256SUMS.txt"}
    found: set[str] = set()
    with ZipFile(path) as archive:
        for name in archive.namelist():
            found.add(Path(name).name)
            parts = Path(name).parts
            lowered = name.casefold()
            if (any(part in {"data", "generated_agents", ".venv"} for part in parts)
                    or any(part in {".env", "credentials.env", "local_settings.json"} for part in parts)
                    or lowered.endswith((".sqlite3", ".log"))):
                forbidden.append(name)
            content = archive.read(name)
            if secrets and any(secret in content for secret in secrets):
                leaks.append(name)
            if name.endswith(".whl"):
                with ZipFile(io.BytesIO(content)) as nested:
                    for nested_name in nested.namelist():
                        nested_content = nested.read(nested_name)
                        if secrets and any(secret in nested_content for secret in secrets):
                            leaks.append(f"{name}!{nested_name}")
    return forbidden, leaks, sorted(required - found)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheel", type=Path)
    parser.add_argument("--bundle", type=Path)
    args = parser.parse_args()
    secrets = local_secrets()
    report = {"local_secrets_checked": len(secrets), "source_leaks": source_leaks(secrets)}
    if args.wheel:
        forbidden, leaks, skills = wheel_audit(args.wheel, secrets)
        report.update({"wheel": args.wheel.name, "forbidden_entries": forbidden,
                       "wheel_secret_leaks": leaks, "bundled_skill_files": skills})
    if args.bundle:
        forbidden, leaks, missing = bundle_audit(args.bundle, secrets)
        report.update({"bundle": args.bundle.name, "bundle_forbidden_entries": forbidden,
                       "bundle_secret_leaks": leaks, "bundle_missing_files": missing})
    print(json.dumps(report, indent=2))
    problems = (report["source_leaks"] or report.get("forbidden_entries")
                or report.get("wheel_secret_leaks") or report.get("bundle_forbidden_entries")
                or report.get("bundle_secret_leaks") or report.get("bundle_missing_files"))
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
