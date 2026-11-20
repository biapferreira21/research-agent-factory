"""Executar um verificador de confiança em Python separado. Não é uma sandbox."""
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path


class AcceptanceExecutionError(RuntimeError):
    """Infraestrutura do verificador falhou; não pedir reparação ao builder."""


class PythonAcceptance:
    def __init__(self, script: Path, *, timeout_seconds: float = 30):
        if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 120:
            raise ValueError("Timeout deve estar entre 0 e 120 segundos.")
        self.script = script.resolve(strict=True)
        if not self.script.is_file() or self.script.suffix.lower() != ".py":
            raise ValueError("O verificador deve ser um ficheiro Python.")
        self.timeout_seconds = timeout_seconds
        self.sha256 = hashlib.sha256(self.script.read_bytes()).hexdigest()

    def __call__(self, workspace: Path) -> list[str]:
        workspace = workspace.resolve(strict=True)
        if not workspace.is_dir() or self.script.is_relative_to(workspace):
            raise AcceptanceExecutionError("O verificador deve ficar fora do workspace gerado.")
        try:
            current_hash = hashlib.sha256(self.script.read_bytes()).hexdigest()
            if current_hash != self.sha256:
                raise AcceptanceExecutionError("O verificador mudou desde a configuração.")
            completed = subprocess.run(
                [sys.executable, "-I", str(self.script), str(workspace)],
                cwd=self.script.parent, stdin=subprocess.DEVNULL,
                capture_output=True, timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired:
            raise AcceptanceExecutionError("Timeout do verificador de aceitação.") from None
        except OSError:
            raise AcceptanceExecutionError("Não foi possível executar o verificador.") from None
        if completed.returncode != 0:
            raise AcceptanceExecutionError("O processo do verificador terminou com erro.")
        if len(completed.stdout) > 64000:
            raise AcceptanceExecutionError("Resposta do verificador excede 64000 bytes.")
        try:
            payload = json.loads(completed.stdout.decode("utf-8"))
        except (ValueError, UnicodeError):
            raise AcceptanceExecutionError("Resposta JSON inválida do verificador.") from None
        if (not isinstance(payload, dict) or set(payload) != {"errors"} or
                not isinstance(payload["errors"], list) or
                any(not isinstance(item, str) or not item.strip() for item in payload["errors"])):
            raise AcceptanceExecutionError("Esperado objeto JSON com errors: list[str].")
        return payload["errors"]

    def audit_metadata(self) -> dict:
        """Configuração esperada; não ler variáveis de ambiente nem guardar código."""
        return {"kind": "python_process", "script": str(self.script),
                "script_sha256": self.sha256, "timeout_seconds": self.timeout_seconds,
                "python_executable": sys.executable, "python_version": sys.version,
                "adapter_version": 1}
