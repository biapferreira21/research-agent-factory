"""Persistência local de projetos, documentos, jobs e mensagens em SQLite."""
from datetime import datetime, timezone
from contextlib import contextmanager
import hashlib
import io
import json
from pathlib import Path
import shutil
import sqlite3
from uuid import UUID, uuid4

from app.retrieval.bm25 import rank


def now():
    return datetime.now(timezone.utc).isoformat()


class ProjectStore:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.database = self.root / "factory.sqlite3"
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY, name TEXT NOT NULL,
                  question TEXT NOT NULL, domain TEXT NOT NULL, created TEXT NOT NULL, skills TEXT NOT NULL DEFAULT '[]');
                CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                  name TEXT NOT NULL, sha256 TEXT NOT NULL, size INTEGER NOT NULL, created TEXT NOT NULL,
                  chunks TEXT NOT NULL, UNIQUE(project_id,sha256));
                CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                  kind TEXT NOT NULL, status TEXT NOT NULL, created TEXT NOT NULL, result TEXT, error TEXT, progress TEXT);
                CREATE TABLE IF NOT EXISTS messages(id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
                  role TEXT NOT NULL, content TEXT NOT NULL, created TEXT NOT NULL, agent_id TEXT);
            ''')
            columns = {row[1] for row in db.execute("PRAGMA table_info(messages)")}
            if "agent_id" not in columns:
                db.execute("ALTER TABLE messages ADD COLUMN agent_id TEXT")
            job_columns = {row[1] for row in db.execute("PRAGMA table_info(jobs)")}
            if "progress" not in job_columns:
                db.execute("ALTER TABLE jobs ADD COLUMN progress TEXT")

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.database, timeout=20)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def directory(self, project_id):
        identifier = str(UUID(project_id))
        path = (self.root / "projects" / identifier).resolve()
        if not path.is_relative_to(self.root):
            raise ValueError("Project is outside the data root")
        return path

    def create(self, name, question, domain="general"):
        if not name.strip() or not question.strip() or len(question) > 10000 or len(name) > 150:
            raise ValueError("Name and question are required; question limit is 10,000 characters")
        identifier = str(uuid4())
        with self.connect() as db:
            db.execute("INSERT INTO projects(id,name,question,domain,created) VALUES(?,?,?,?,?)",
                       (identifier, name.strip(), question.strip(), domain.strip(), now()))
        self.directory(identifier).mkdir(parents=True, exist_ok=True)
        return self.project(identifier)

    def project(self, identifier):
        self.directory(identifier)
        with self.connect() as db:
            row = db.execute("SELECT * FROM projects WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise FileNotFoundError("Project not found")
        result = dict(row)
        result["skills"] = json.loads(result["skills"])
        return result

    def projects(self):
        with self.connect() as db:
            rows = db.execute("SELECT id FROM projects ORDER BY created DESC").fetchall()
        return [self.project(row["id"]) for row in rows]

    def set_skills(self, identifier, skills):
        self.project(identifier)
        with self.connect() as db:
            db.execute("UPDATE projects SET skills=? WHERE id=?", (json.dumps(skills), identifier))

    def set_question(self, identifier, question):
        self.project(identifier)
        question = str(question).strip()
        if not question or len(question) > 10000:
            raise ValueError("Research question must contain 1 to 10,000 characters")
        with self.connect() as db:
            db.execute("UPDATE projects SET question=? WHERE id=?", (question, identifier))

    def documents(self, identifier):
        self.project(identifier)
        with self.connect() as db:
            rows = db.execute("SELECT id,name,sha256,size,created FROM documents WHERE project_id=? ORDER BY created DESC",
                              (identifier,)).fetchall()
        return [dict(row) for row in rows]

    def add_document(self, identifier, name, raw):
        self.project(identifier)
        name = Path(name.replace("\\", "/")).name
        suffix = Path(name).suffix.lower()
        if suffix not in (".txt", ".md", ".pdf", ".docx", ".csv", ".json") or not raw or len(raw) > 20_000_000:
            raise ValueError("Use TXT, MD, PDF, DOCX, CSV or JSON up to 20 MB")
        digest = hashlib.sha256(raw).hexdigest()
        with self.connect() as db:
            row = db.execute("SELECT id FROM documents WHERE project_id=? AND sha256=?", (identifier, digest)).fetchone()
        if row:
            return {"id": row["id"], "duplicate": True}
        if suffix == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(io.BytesIO(raw))
            if reader.is_encrypted or len(reader.pages) > 400:
                raise ValueError("Encrypted PDF or more than 400 pages")
            pages = [(i + 1, page.extract_text() or "") for i, page in enumerate(reader.pages)]
        elif suffix == ".docx":
            from zipfile import ZipFile
            with ZipFile(io.BytesIO(raw)) as archive:
                if sum(item.file_size for item in archive.infolist()) > 50_000_000:
                    raise ValueError("Expanded DOCX exceeds 50 MB")
            from docx import Document
            doc = Document(io.BytesIO(raw))
            text = "\n".join(p.text for p in doc.paragraphs)
            text += "\n" + "\n".join(" | ".join(cell.text for cell in row.cells) for table in doc.tables for row in table.rows)
            pages = [(None, text)]
        else:
            text = raw.decode("utf-8-sig")
            if suffix == ".json":
                json.loads(text)  # O original estruturado é preservado, nunca substituído pelo texto.
            pages = [(None, text)]
        if sum(len(text) for _, text in pages) > 2_000_000:
            raise ValueError("Extracted text exceeds two million characters")
        chunks = []
        for page, text in pages:
            for offset in range(0, len(text), 1400):
                part = text[offset:offset + 1600].strip()
                if part:
                    chunks.append({"text": part, "page": page, "offset": offset, "number": len(chunks) + 1})
        if not chunks:
            raise ValueError("No extractable text; scanned PDFs need external OCR")
        document_id = str(uuid4())
        directory = self.directory(identifier) / "documents"
        directory.mkdir(exist_ok=True)
        (directory / (document_id + suffix)).write_bytes(raw)
        with self.connect() as db:
            db.execute("INSERT INTO documents VALUES(?,?,?,?,?,?,?)",
                       (document_id, identifier, name, digest, len(raw), now(), json.dumps(chunks, ensure_ascii=False)))
        return {"id": document_id, "name": name, "chunks": len(chunks), "sha256": digest, "duplicate": False}

    def source(self, identifier, document_id):
        self.project(identifier)
        with self.connect() as db:
            row = db.execute("SELECT * FROM documents WHERE project_id=? AND id=?", (identifier, document_id)).fetchone()
        if row is None:
            raise FileNotFoundError("Document not found")
        path = self.directory(identifier) / "documents" / (str(UUID(document_id)) + Path(row["name"]).suffix.lower())
        if not path.resolve().is_relative_to(self.directory(identifier)):
            raise ValueError("Document is outside this project")
        return path, row["name"]

    def chunks(self, identifier):
        self.project(identifier)
        with self.connect() as db:
            rows = db.execute("SELECT * FROM documents WHERE project_id=?", (identifier,)).fetchall()
        return [{**chunk, "document_id": row["id"], "source": row["name"], "sha256": row["sha256"],
                 "citation": f"{row['id']}:{chunk['number']}"}
                for row in rows for chunk in json.loads(row["chunks"])]

    def search(self, identifier, query, limit=8):
        chunks = self.chunks(identifier)
        return [{**chunks[i], "score": score} for i, score in rank(query, [c["text"] for c in chunks], limit=limit)]

    def job(self, identifier):
        with self.connect() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (identifier,)).fetchone()
        if row is None:
            raise FileNotFoundError("Operation not found")
        data = dict(row)
        data["result"] = json.loads(data["result"]) if data["result"] else None
        return data

    def jobs(self, project_id):
        self.project(project_id)
        with self.connect() as db:
            rows = db.execute("SELECT id FROM jobs WHERE project_id=? ORDER BY created DESC", (project_id,)).fetchall()
        return [self.job(row["id"]) for row in rows]

    def start_job(self, project_id, kind):
        self.project(project_id)
        identifier = str(uuid4())
        with self.connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT id FROM jobs WHERE project_id=? AND status IN ('queued','running')", (project_id,)).fetchone():
                raise ValueError("An operation is already running in this project")
            db.execute("INSERT INTO jobs(id,project_id,kind,status,created) VALUES(?,?,?,?,?)",
                       (identifier, project_id, kind, "queued", now()))
        return identifier

    def update_job(self, identifier, status, result=None, error=None, progress=None):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status=?,result=?,error=?,progress=COALESCE(?,progress) WHERE id=?",
                       (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
                        error, progress, identifier))

    def update_job_if_active(self, identifier, status, result=None, error=None, progress=None):
        """Update a job only while it is still owned by its worker.

        A watchdog can close a provider call while its Python worker is still
        unwinding. Conditional updates prevent that late worker from reopening
        a failed operation or replacing a newer retry's state.
        """
        with self.connect() as db:
            cursor = db.execute(
                "UPDATE jobs SET status=?,result=?,error=?,progress=COALESCE(?,progress) "
                "WHERE id=? AND status IN ('queued','running')",
                (status, json.dumps(result, ensure_ascii=False) if result is not None else None,
                 error, progress, identifier),
            )
        return cursor.rowcount == 1

    def delete_job(self, project_id, identifier):
        """Delete a terminal operation and its project-scoped build artifacts."""
        self.project(project_id)
        item = self.job(identifier)
        if item["project_id"] != project_id:
            raise FileNotFoundError("Operation not found")
        if item["status"] in {"queued", "running"}:
            raise ValueError("Wait for the running operation before deleting it")
        project_directory = self.directory(project_id)
        paths = []
        result = item.get("result") or {}
        for raw in (result.get("workspace"), result.get("telemetry_path")):
            if not raw:
                continue
            path = Path(raw).resolve()
            if not path.is_relative_to(project_directory):
                raise ValueError("Operation artifacts are outside this project")
            paths.append(path)
        with self.connect() as db:
            db.execute("DELETE FROM messages WHERE project_id=? AND agent_id=?", (project_id, identifier))
            db.execute("DELETE FROM jobs WHERE project_id=? AND id=?", (project_id, identifier))
        for path in sorted(set(paths), key=lambda item: len(item.parts), reverse=True):
            if path.exists() and not path.is_symlink():
                if path.is_dir():
                    shutil.rmtree(path)
                else:
                    path.unlink()
        return item

    def delete_project(self, identifier):
        """Delete one inactive project and everything stored below its directory."""
        project = self.project(identifier)
        if any(job["status"] in {"queued", "running"} for job in self.jobs(identifier)):
            raise ValueError("Wait for the running operation before deleting this project")
        directory = self.directory(identifier)
        if directory.exists() and not directory.is_symlink():
            shutil.rmtree(directory)
        with self.connect() as db:
            db.execute("DELETE FROM messages WHERE project_id=?", (identifier,))
            db.execute("DELETE FROM documents WHERE project_id=?", (identifier,))
            db.execute("DELETE FROM jobs WHERE project_id=?", (identifier,))
            db.execute("DELETE FROM projects WHERE id=?", (identifier,))
        return project

    def recover_jobs(self):
        with self.connect() as db:
            db.execute("UPDATE jobs SET status='interrupted',error='Server restarted; operation was not resumed' WHERE status IN ('queued','running')")

    def message(self, project_id, role, content, agent_id=None):
        self.project(project_id)
        if agent_id is not None:
            agent = self.job(agent_id)
            if agent["project_id"] != project_id or agent["kind"] not in {"build", "chat", "agent_chat"}:
                raise ValueError("Agent does not belong to this project")
        with self.connect() as db:
            db.execute("INSERT INTO messages(id,project_id,role,content,created,agent_id) VALUES(?,?,?,?,?,?)",
                       (str(uuid4()), project_id, role, content, now(), agent_id))

    def messages(self, project_id):
        self.project(project_id)
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT messages.* FROM messages "
                "LEFT JOIN jobs ON jobs.id=messages.agent_id AND jobs.project_id=messages.project_id "
                "WHERE messages.project_id=? AND (messages.agent_id IS NULL OR jobs.kind='chat') "
                "ORDER BY messages.created", (project_id,))]

    def agent_messages(self, project_id, agent_id):
        self.project(project_id)
        agent = self.job(agent_id)
        if agent["project_id"] != project_id or agent["kind"] != "build":
            raise ValueError("Agent does not belong to this project")
        with self.connect() as db:
            return [dict(row) for row in db.execute(
                "SELECT * FROM messages WHERE project_id=? AND agent_id=? ORDER BY created", (project_id, agent_id))]
