# Etapa 7H — associar avaliações a builds científicos

`archive_build_results` liga medições fornecidas pelo chamador a um build
científico terminado. Não executa o agente gerado nem experiências.

## Ordem de estudo

1. Em `app/schemas/results.py`, observa `source_build_id`, um UUID opcional.
   Avaliações independentes continuam possíveis. Ao associar a um build, o
   identificador passa a fazer parte do ficheiro de resultados protegido pelo
   hash do arquivo.
2. Lê `app/planning/build_evaluation.py`. O argumento `factory_root` é a raiz
   que contém `.factory_runs`; `build_id` tem de ser um UUID. A função não recebe
   um caminho arbitrário para o protocolo.
3. A função lê os eventos e exige que o último marque `finished/passed`, com
   identificadores consistentes. Depois carrega protocolo e AgentSpec da pasta
   de telemetria e compara o hash do protocolo com o registado no AgentSpec.
4. Verifica também o hash nas medições e recusa medições associadas a outro build.
   Não recalcula esse campo para aceitar resultados de outro protocolo.
5. Cria uma cópia das medições com o vínculo e usa `save_evaluation`. O arquivo
   fica em `.research_evaluations/<uuid>` sob a raiz da factory. Não altera o
   estado do build nem escreve no workspace do builder.
6. Lê `tests/test_build_evaluation.py`: inclui vínculo, preservação dos ficheiros,
   falhas de build, IDs inválidos e resultados de outro protocolo/build.

## Utilização com resultados já carregados

```python
from pathlib import Path
from app.planning.build_evaluation import archive_build_results
from app.planning.result_store import load_evaluation
from app.schemas.results import ExperimentResults

# Usa o ID devolvido pelo teu build_research e um ficheiro de medições existente.
# results = ExperimentResults.model_validate_json(Path("measurements.json").read_text(encoding="utf-8"))
# archive = archive_build_results(Path("generated_agents"), build_id, results)
# loaded = load_evaluation(archive)
```

```powershell
.venv\Scripts\python.exe -m pytest tests/test_build_evaluation.py -q
```

## Interpretação e limites

Um build `passed` significa que passou os gates e testes de geração; não significa
que a experiência foi executada. Resultados sintéticos continuam sintéticos.
Medições incompletas podem ser arquivadas com `invalid_results` para diagnóstico,
desde que pertençam ao protocolo e build corretos.

A identidade é uma associação declarada verificada por consistência, não prova
criptográfica da execução. Logs locais e contratos ainda não são assinados.
O arquivo inclui o protocolo e o UUID do build, mas não copia o código gerado,
dataset ou todos os logs. Não há isolamento de execução nem orçamento experimental.

Uma build de outra versão cujo hash de protocolo já não corresponda à serialização
atual será recusada. A migração de protocolos antigos permanece explícita.
Arquivos independentes antigos sem `source_build_id` continuam a ser lidos com
esse campo a `None`; o relatório de avaliação não depende desse campo.
