# Etapa 8G — resultado final persistente

Cada build novo guarda agora `build_result.json` na pasta de telemetria
`.factory_runs/<uuid>`, fora do workspace do builder.

## Ordem de estudo

1. Em `app/builder/harness.py`, lê `BuildResult.to_dict`. Converte o resultado
   em dados JSON com `format_version=1`. Os custos Decimal são serializados
   pelo contrato de custos, preservando a representação decimal.
2. O ficheiro reúne ID, nome do agente, workspace, estado, erros, reparações,
   pasta de telemetria e resumo de custos. Campos ainda não disponíveis ficam
   vazios, por exemplo workspace quando o planner é bloqueado.
3. Segue o `finally` de `_build`: após finalizar a telemetria, constrói o mesmo
   objeto que será devolvido ao chamador e persiste a sua representação.
4. Exceções inesperadas continuam a propagar-se. O ficheiro guarda apenas
   `Unexpected failure: TipoDoErro`, não a mensagem externa. Falhas de validação
   e bloqueios mantêm os diagnósticos já apresentados pelo harness; estes podem
   incluir texto dos testes e devem ser tratados como dados potencialmente privados.
5. A escrita usa `build_result.json.tmp` e renomeação para o nome final. Uma
   interrupção antes da publicação pode deixar um temporário. Não o interpretes
   como um resultado final nem o publiques automaticamente.
6. Lê `tests/test_persisted_build_result.py`: compara o ficheiro com o objeto
   devolvido, e verifica sucesso, falha, bloqueio precoce e exceções inesperadas.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_persisted_build_result.py -q
```

Depois de executar um build, podes ler o resultado diretamente:

```python
import json
from pathlib import Path

# result é o BuildResult devolvido pelo harness.
# saved = json.loads((Path(result.telemetry_path) / "build_result.json").read_text(encoding="utf-8"))
```

## Limites

Builds antigos não recebem este ficheiro retroativamente. O comando de consulta
continua a interpretar os eventos para suportar esses builds e detetar logs
incompletos; não passa a confiar automaticamente neste ficheiro.

A renomeação evita publicar um JSON parcialmente escrito, mas não oferece
transação conjunta com events/cost_summary nem garantia de durabilidade por fsync.
Erros ao finalizar telemetria ou gravar no disco podem impedir a persistência.
Um encerramento abrupto do processo também pode evitar que o `finally` execute.

Este é um resultado consultável, não um checkpoint de execução. Não guarda o
estado interno do agente, não restaura reservas de custo e não permite retoma.
O estado `passed` continua a referir-se à geração/validação do projeto, não ao
sucesso de uma experiência científica.
