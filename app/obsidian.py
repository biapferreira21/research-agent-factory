"""Bidirectional Markdown bridge between project memory and an Obsidian vault."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from app.wiki import ProjectWiki


def _slug(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip()).strip("-.")
    return value[:80] or "research"


class ObsidianBridge:
    """Mirror project notes and import new Markdown notes as agent memory."""

    def __init__(self, data_root: Path):
        self.data_root = Path(data_root).resolve()
        self.data_root.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.data_root / "local_settings.json"

    def _settings(self) -> dict:
        if not self.settings_path.is_file() or self.settings_path.is_symlink():
            return {}
        try:
            data = json.loads(self.settings_path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
        except (OSError, ValueError):
            return {}

    def _save(self, data: dict) -> None:
        descriptor, temporary = tempfile.mkstemp(prefix="settings-", suffix=".tmp", dir=self.data_root)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(data, stream, ensure_ascii=False, indent=2)
                stream.write("\n")
            os.replace(temporary, self.settings_path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def status(self) -> dict:
        raw = self._settings().get("obsidian_vault")
        path = Path(raw).expanduser() if raw else None
        available = bool(path and path.is_absolute() and path.is_dir() and not path.is_symlink())
        return {"connected": available, "path": str(path) if available else None}

    def connect(self, path: str) -> dict:
        vault = Path(path).expanduser()
        if not vault.is_absolute():
            raise ValueError("Use an absolute Obsidian vault path")
        try:
            vault = vault.resolve(strict=True)
        except OSError as error:
            raise ValueError("Obsidian vault folder was not found") from error
        if not vault.is_dir() or vault.is_symlink():
            raise ValueError("Obsidian vault must be a local folder")
        probe = vault / ".raf-write-test"
        try:
            probe.write_text("ok", encoding="utf-8")
            probe.unlink()
        except OSError as error:
            raise ValueError("Obsidian vault is not writable") from error
        settings = self._settings()
        settings["obsidian_vault"] = str(vault)
        self._save(settings)
        return self.status()

    def disconnect(self) -> dict:
        settings = self._settings()
        settings.pop("obsidian_vault", None)
        self._save(settings)
        return self.status()

    def _project_root(self, project: dict) -> Path:
        status = self.status()
        if not status["connected"]:
            raise ValueError("Connect an Obsidian vault first")
        vault = Path(status["path"]).resolve(strict=True)
        folder = (vault / "Research Agent Factory" /
                  f"{_slug(project['name'])}-{project['id'][:8]}").resolve()
        if not folder.is_relative_to(vault):
            raise ValueError("Invalid Obsidian project path")
        folder.mkdir(parents=True, exist_ok=True)
        return folder

    @staticmethod
    def _manifest(project_directory: Path) -> tuple[Path, dict]:
        path = project_directory / "obsidian_sync.json"
        if path.is_file() and not path.is_symlink():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                return path, data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                pass
        return path, {}

    def sync(self, project: dict, project_directory: Path) -> dict:
        root = self._project_root(project)
        wiki = ProjectWiki(project_directory)
        manifest_path, manifest = self._manifest(project_directory)
        imported = 0
        exported = 0

        # User-authored Markdown becomes ordinary project memory. A content
        # digest stops unchanged notes from being imported more than once.
        imports = manifest.setdefault("imports", {})
        for note in sorted(root.glob("*.md"))[:100]:
            if note.is_symlink() or note.name == "Home.md" or note.name.startswith("RAF-"):
                continue
            if note.stat().st_size > 1_000_000:
                continue
            raw = note.read_bytes()
            digest = hashlib.sha256(raw).hexdigest()
            relative = note.name
            if imports.get(relative) == digest:
                continue
            content = raw.decode("utf-8-sig").strip()
            if content:
                title = re.sub(r"^#\s+", "", content.splitlines()[0]).strip() or note.stem
                wiki.add(title[:160], f"Obsidian: `{relative}`\n\n{content}"[:50_000])
                imported += 1
            imports[relative] = digest

        entries = wiki.entries()
        for item in entries:
            target = root / f"RAF-{item['id']}.md"
            body = (f"---\nraf_id: {item['id']}\nkind: {item['kind']}\n"
                    f"created: {item['created']}\n---\n\n# {item['title']}\n\n{item['content']}\n")
            if not target.exists() or target.read_text(encoding="utf-8") != body:
                target.write_text(body, encoding="utf-8")
                exported += 1
        links = "\n".join(f"- [[RAF-{item['id']}|{item['title']}]]" for item in entries)
        (root / "Home.md").write_text(
            f"# {project['name']}\n\n## Question\n\n{project['question']}\n\n## Memory\n\n{links}\n",
            encoding="utf-8",
        )
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return {"connected": True, "folder": str(root), "imported": imported,
                "exported": exported, "entries": len(entries)}
