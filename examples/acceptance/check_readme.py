"""Verificação didática de entrega; não executa nem importa o agente gerado."""
import json
import sys
from pathlib import Path


workspace = Path(sys.argv[1])
errors = [] if (workspace / "README.md").is_file() else ["README.md is required"]
# Falha de requisito usa errors; exit code diferente de zero significa falha do verificador.
print(json.dumps({"errors": errors}))
