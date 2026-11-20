# Etapa 3 — progresso, custos e orçamento

Atualização após a etapa 4A: o Model Registry já calcula reservas automaticamente
e estima custo pelos tokens quando não há custo reportado. A reserva manual deixou
de ser obrigatória. As descrições abaixo documentam a base criada nesta etapa;
consulta `ETAPA_04.md` para o comportamento atual da integração de preços.

O limite escolhido é USD 1,00 por build. Cada build tem uma conta independente.
Ainda não existe sessão de investigação no runtime: o seu orçamento separado
será integrado quando essa sessão existir. Não foram feitas chamadas pagas nesta etapa.

## 1. Descrever o que vamos guardar

Lê `app/telemetry/schemas.py`:

- `BuildStage`: nomes fixos das etapas (planning, preparing, generating, gates, tests, finished).
- `BuildEvent`: início/resultado de uma etapa, data UTC, duração e resumo de custos.
- `UsageRecord`: provider, modelo, tokens, duração, reserva e custo de uma chamada.
- `CostSummary`: montante reportado, estimado, reservado, desconhecidos e saldo.

Usamos `Decimal` para dinheiro: `Decimal("0.10")` preserva o valor decimal exato.
`None` significa desconhecido. `Decimal("0")` significa zero conhecido. Uma
reserva é uma previsão para autorizar a chamada; não é uma despesa medida.
O campo `actual_cost_usd` significa custo reportado pelo provider, sem auditoria
posterior da fatura. O terminal usa a palavra “reportado” por esse motivo.

## 2. Reservar e reconciliar

Em `app/telemetry/costs.py`, segue `reserve` → `settle` → `summary`:

1. Antes da chamada, verificar se a reserva cabe no saldo.
2. Contabilizar reservas ativas para não autorizar duas chamadas com o mesmo dinheiro.
3. Depois da chamada, substituir a reserva pelo custo reportado ou por uma
   estimativa de custo explicitamente fornecida; sem ambos, registar desconhecido.
4. Se houver um custo desconhecido, bloquear novas chamadas num tracker com limite.
5. Se o custo exceder o orçamento, guardá-lo integralmente e bloquear a continuação.

`RLock` protege as alterações de estado contra callbacks concorrentes. O código
usa um ID único por chamada para rejeitar reservas e contabilizações repetidas.
Não há mecanismo de retoma/reconciliação tardia nesta etapa.

Experimenta com números fictícios:

```powershell
.\.venv\Scripts\python.exe budget_demo.py
```

O demo reserva 0,60, regista um custo fictício de 0,25 e recusa uma nova reserva
de 0,80, porque restam 0,75. Não usa APIs.

## 3. Guardar progresso por etapa

Em `app/telemetry/build.py`, `stage(...)` é um context manager:

```python
with telemetry.stage(BuildStage.PLANNING):
    spec = planner(requirement)
```

Emite `started` antes do trabalho e `passed` ou `failed` no fim. Uma recusa do
orçamento produz `blocked`. O harness transforma falhas de gates/pytest em eventos
de falha; “o processo acabou” não basta para marcar sucesso.

`perf_counter()` mede duração. `ContextVar` disponibiliza a telemetria do build
ativo à criação dos modelos, sem uma variável global partilhada entre builds.
O token devolvido por `set` permite repor o contexto em `finally`, mesmo com erro.

Os logs ficam em `generated_agents/.factory_runs/<build_id>/`:

- `events.jsonl`: um evento JSON por linha, acrescentado durante a execução.
- `usage.jsonl`: uma chamada concluída/falhada por linha; só existe se houver chamadas.
- `cost_summary.json`: resumo final, incluindo builds bloqueados ou com exceções.

A pasta fica fora da raiz das ferramentas desse builder. Os eventos não guardam
prompts, respostas, API keys nem mensagens completas de exceções; guardam o tipo
da exceção. O AgentSpec continua no projeto gerado, como antes. Os logs não são
um registo inviolável contra código Python executado localmente.

## 4. Observar as chamadas aos modelos

Em `app/telemetry/callbacks.py`, `UsageCallback` adapta os eventos do LangChain:

- `on_chat_model_start`: reservar antes de executar.
- `on_llm_end`: recolher tokens e custo reportado, quando disponíveis.
- `on_llm_error`: registar falha com custo desconhecido; uma falha não prova custo zero.

`raise_error=True` faz uma recusa interromper a execução, em vez de ser ignorada.
As assinaturas foram conferidas no pacote instalado e na
[referência oficial de callbacks](https://reference.langchain.com/python/langchain-core/callbacks/base/BaseCallbackHandler).
Há testes com `FakeListChatModel` que verificam esta interrupção no LangChain real.

`app/models.py` instala o callback quando existe um build ativo. Nesse contexto,
desativa retries internos dos clientes para não esconder tentativas faturáveis.
Retries explícitos futuros terão reservas e IDs próprios. Modelos criados fora
do harness e clientes externos que não usem `get_model()` não são monitorizados.

## 5. Configuração e limites reais desta etapa

`BUILD_BUDGET_USD` tem default `1.00`. A configuração opcional
`MODEL_CALL_RESERVATION_USD` define a reserva por chamada. Não foi atribuído um
valor arbitrário: falta o Model Registry para estimar com base em modelo, tokens
e preços. Sem reserva configurada, o harness bloqueia chamadas a modelos antes
da execução. O demo offline funciona porque não chama modelos.

A reserva fixa é uma previsão, não um limite de faturação imposto ao provider.
Uma chamada em curso pode custar mais; se isso acontecer, registamos o excesso
e interrompemos novas chamadas. Uma garantia estrita de despesa exige limites
no fornecedor e estimativas superiores conservadoras ligadas a limites de tokens.
Não apresentamos esta proteção como garantia de uma fatura máxima de USD 1,00.

O adaptador lê `usage_metadata` e o campo `response_metadata.cost` quando este
existe. Não inventa preços para OpenAI ou OpenRouter. Quando não recebe custo,
guarda desconhecido e bloqueia a chamada seguinte, mesmo que tenha recebido tokens.
A integração de estimativas por tokens/preços faz parte do próximo Model Registry.

`UsageRecord` já permite registos de ferramentas pagas, mas não há MCPs pagos
integrados. Portanto ainda não existe contabilização automática de custos de MCPs.
Falhas abruptas do processo podem deixar apenas os eventos já gravados; não há
retoma automática de reservas nem recuperação após crash nesta etapa.

## 6. Executar e estudar

```powershell
.\.venv\Scripts\python.exe harness_offline_demo.py
.\.venv\Scripts\python.exe budget_demo.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

Ordem de leitura sugerida: schemas → costs → budget_demo → build → callbacks → harness.
O demo do harness mostra etapas no terminal e indica a pasta dos logs. Custo zero
nesse demo significa que não houve chamadas a modelos; não inclui eletricidade
ou tempo de CPU local. Os testes novos estão em `test_cost_tracker.py`,
`test_telemetry.py` e `test_usage_callback.py`.

Exercício: muda o custo fictício de 0,25 para 0,90 no budget_demo e observa o saldo.
Depois remove `actual_cost_usd` e observa a diferença entre desconhecido e zero.
