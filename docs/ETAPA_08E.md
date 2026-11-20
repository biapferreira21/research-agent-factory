# Etapa 8E — consultar builds guardados

`build_report.py` apresenta um relatório JSON sem executar modelos, testes,
verificadores ou código gerado. Recebe o UUID de um build existente.

```powershell
.venv\Scripts\python.exe build_report.py UUID_DO_BUILD
.venv\Scripts\python.exe build_report.py UUID_DO_BUILD --root generated_agents
```

Substitui `UUID_DO_BUILD` pelo identificador devolvido pelo harness ou pelo nome
da pasta em `generated_agents/.factory_runs`. Sem `--root`, usa a raiz configurada.

## Ordem de estudo

1. Lê `app/telemetry/report.py`: valida o UUID e limita a leitura à raiz indicada.
2. `records` lê JSONL linha a linha, com limite de 10 MB por log. Linhas inválidas
   são assinaladas. Eventos também passam pelo contrato `BuildEvent`.
3. Um último evento `finished` fornece o estado final. Sem esse evento, o estado
   é `incomplete`: pode ser um build ainda em curso ou interrompido. Logs inválidos
   produzem `unreliable_logs`, sem apresentar uma aprovação como fiável.
4. Os custos vêm do último evento válido, com o nome `costs_at_last_event`.
   Podem estar desatualizados num build em curso. Reservas não são cobranças.
5. As reparações são contadas pelos eventos `repairing/started`, não por chamadas
   ou correções bem-sucedidas. Incluem etapas bloqueadas antes de chamar o builder.
6. O relatório inclui o último registo de aceitação e quantos existem. A ausência
   de registos não significa aprovação; pode significar etapa não configurada
   ou ainda não alcançada. Estes registos são dados locais, não assinados.
7. Para cada arquivo em `.research_evaluations`, verifica a integridade e recalcula
   a avaliação antes de incluir resultados cujo `source_build_id` corresponde.
   Arquivos inválidos são avisos gerais: não se consegue atribuí-los com confiança
   a este build. Não alteram o estado da geração, que é distinto da investigação.
8. Lê `tests/test_build_report.py`: inclui interrupção, corrupção e avaliação
   associada cujo ficheiro foi alterado.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_build_report.py -q
```

## Limites

O comando é apenas de leitura. Exit code 0 significa que conseguiu apresentar o
relatório, não que o build passou; consulta `status` e `issues`. Erros de leitura
ou argumentos inválidos devolvem código 2.

Não há listagem, dashboard, retomada ou reparação através deste comando. A leitura
não é uma transação: logs que estejam a ser escritos podem parecer incompletos.
O scan dos arquivos é linear e não copia datasets ou código. A integridade local
não prova autenticidade, qualidade científica ou execução real das medições.
