"""Local Markdown research journal; readable as an Obsidian vault."""
from datetime import datetime, timezone
import io
import json
from pathlib import Path
from uuid import UUID, uuid4
from zipfile import ZipFile, ZIP_DEFLATED


class ProjectWiki:
    def __init__(self, project_directory: Path):
        self.root = (project_directory / "wiki").resolve()
        if not self.root.is_relative_to(project_directory.resolve()):
            raise ValueError("Wiki outside project")
        self.root.mkdir(parents=True, exist_ok=True)

    def entries(self):
        entries = []
        for path in self.root.glob("*.md"):
            if path.is_symlink() or path.stat().st_size > 100_000:
                continue
            try:
                content = path.read_text(encoding="utf-8")
                meta, body = content.split("\n---\n", 1)
                info = json.loads(meta.removeprefix("<!--\n").removesuffix("\n-->"))
                if str(UUID(info["id"])) != path.stem:
                    continue
                heading = "# " + info["title"].replace("\n", " ") + "\n\n"
                if body.startswith(heading):
                    body = body[len(heading):]
                entries.append({**info, "content": body.strip()})
            except (ValueError, KeyError, OSError, UnicodeError):
                continue
        return sorted(entries, key=lambda item: item["created"], reverse=True)

    def add(self, title: str, content: str, *, kind="note", agent_id=None):
        title, content = title.strip(), content.strip()
        if not title or len(title) > 160 or not content or len(content) > 50_000:
            raise ValueError("Title and content are required; note limit is 50,000 characters")
        if kind not in {"note", "source", "build", "evaluation", "skill", "checkpoint"}:
            raise ValueError("Unknown wiki entry type")
        identifier = str(uuid4())
        info = {"id": identifier, "title": title, "kind": kind,
                "agent_id": agent_id, "created": datetime.now(timezone.utc).isoformat()}
        source = "<!--\n" + json.dumps(info, ensure_ascii=False) + "\n-->\n---\n# " + title.replace("\n", " ") + "\n\n" + content + "\n"
        (self.root / (identifier + ".md")).write_text(source, encoding="utf-8")
        return {**info, "content": content}

    def delete_agent_entries(self, agent_id: str):
        """Remove automatic journal records linked to a deleted agent build."""
        removed = 0
        for item in self.entries():
            if item.get("agent_id") != agent_id:
                continue
            path = self.root / (item["id"] + ".md")
            if path.is_file() and not path.is_symlink():
                path.unlink()
                removed += 1
        return removed

    def export_zip(self):
        output = io.BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            index = ["# Research wiki", "", "Open this folder as an Obsidian vault.", ""]
            for item in self.entries():
                name = item["id"] + ".md"
                index.append(f"- [[{item['id']}|{item['title']}]] — {item['kind']}")
                archive.write(self.root / name, name)
            archive.writestr("Home.md", "\n".join(index) + "\n")
        return output.getvalue()
