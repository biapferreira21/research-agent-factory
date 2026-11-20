# Como estudar esta versão

Segue uma pergunta desde o formulário até aos ficheiros criados. Não precisas de compreender tudo de uma vez.

1. **Entrada — `app/cli.py`, `app/__main__.py`.** `argparse` escolhe o comando. `serve` cria a aplicação FastAPI e inicia Uvicorn. Exercício: corre `python -m app doctor` e identifica de onde vem cada campo.
2. **Interface — `app/static/index.html`, `lab.css`, `lab.js`, `scene.js`.** HTML define a estrutura, CSS o aspeto e JavaScript envia pedidos HTTP. `api()` concentra os pedidos; `state` guarda a vista corrente. `renderProject()` escolhe o separador; `scene.js` usa Three.js local para desenhar geometria animada sobre a imagem fornecida. JavaScript e Java são linguagens diferentes; esta interface usa JavaScript.
3. **API — `app/web.py`.** Os modelos Pydantic validam pedidos; os endpoints chamam serviços. `dispatch()` transforma uma tarefa demorada num job que a interface acompanha. Exercício: segue a criação de um projeto desde o formulário até `store.create()`.
4. **Persistência — `app/projects.py`.** SQLite guarda metadados e trechos; ficheiros originais ficam no disco. O context manager abre, confirma ou reverte a transação, e fecha a ligação. IDs UUID e consultas por projeto mantêm as fontes separadas.
4a. **Wiki — `app/wiki.py`.** Cada projeto tem ficheiros Markdown com entradas identificadas por UUID. A aplicação acrescenta notas de fonte, build, avaliação e skills. A exportação ZIP inclui `Home.md` com links que o Obsidian entende.
5. **Recuperação — `app/retrieval/bm25.py`.** Tokenização normaliza acentos; BM25 combina frequência, raridade e tamanho do documento. `ProjectStore.search()` junta a pontuação às citações. Exercício: adiciona dois textos, pesquisa o mesmo termo e compara a ordem.
6. **Skills — `app/registry/skills.py`.** O catálogo limita os candidatos; hashes verificam as instruções. BM25 propõe candidatos, JEV pode escolher entre eles. O contexto tem limite de tamanho e assinala truncagem. Importar um script não significa executá-lo.
7. **Protocolo — `app/schemas/research.py`, `app/planning/`.** Pydantic representa hipóteses, métricas, seeds e critérios. O hash liga o protocolo ao AgentSpec e às medições.
8. **Construção — `app/builder/harness.py`.** Lê o método principal pela sequência de estágios: planeamento, capacidades, preparação, geração, validação e conclusão. Repara como dependências injetadas permitem testar sem modelos.
9. **Ferramentas — `app/mcp_server.py`, `app/runtime_tools.py`.** O servidor descreve funções por MCP; o cliente inicia o subprocesso, inicializa a sessão e chama uma ferramenta. Os argumentos do modelo não incluem o projeto ao qual o servidor foi associado.
10. **Custos e decisões — `app/telemetry/`, `app/decisions/`.** `ContextVar` associa uma chamada ao build corrente. Reservas precedem chamadas; custos reportados liquidam a reserva. JEV devolve uma escolha estruturada dentro dos candidatos.
11. **Resultados — `app/planning/build_evaluation.py`, `result_evaluation.py`, `result_store.py`.** Verificação do protocolo → cálculo determinístico → arquivo com hashes. A origem `synthetic` permanece explícita.
12. **Testes — `tests/test_product.py` e restantes testes.** Começa pelos de isolamento de documentos, segue o pedido HTTP com TestClient e termina no transporte MCP real. A demonstração usa pytest real e construção determinística.

## Conversar com a factory e os agentes

No separador **Agents** de um projeto, **Talk to the factory** usa `/api/projects/{id}/chat` e `chat()` em `app/project_runtime.py`. Essa conversa ajuda a clarificar o research brief com as fontes e skills do projeto; a criação do agente continua a ser uma ação explícita no botão de build.

Ao abrir um agente, o separador **Chat** usa `/api/projects/{id}/agents/{job_id}/chat` e `agent_chat()`. A função lê o `AgentSpec`, procura evidência BM25 para cada pergunta e pede uma resposta ao modelo configurado no agente. `ProjectStore.agent_messages()` mantém esse histórico ligado apenas ao agente, através da coluna `agent_id`. Segue o fluxo em `app/static/lab.js`, `app/web.py`, `app/project_runtime.py` e `app/projects.py`; `tests/test_agent_chat.py` verifica o isolamento das conversas e o uso do contrato.

Este chat aplica as instruções e o contexto do agente. Quando o pedido precisa de literatura, pode invocar a pesquisa web aprovada sobre arXiv, Crossref, OpenAlex e Semantic Scholar e apresenta as fontes recuperadas. Ainda não importa nem executa diretamente o seu `agent.py`. Os builds de demonstração também não têm um modelo utilizável para conversar; o separador mostra quando o agente não está apto para chat.

O código gerado pode ser consultado na interface. Para estudar a própria factory, começa pelos módulos pequenos antes do harness. A aplicação atual ainda não executa todas as capacidades descritas pelas skills importadas; o README enumera as limitações concretas.

**Exercício concreto:** altera `BUDGET PER BUILD (USD)` na interface. Segue o número por `BuildInput` em `app/web.py`, `run_build()` em `app/project_runtime.py`, `BuilderHarness` em `app/builder/harness.py` e `CostTracker` em `app/telemetry/costs.py`. Depois abre o agente criado e confirma o valor em `cost_summary.json`. Para a memória, escreve uma nota na wiki, cria um novo build offline e compara `retrieval_snapshot.json` dos dois agentes; o segundo inclui a nota que já existia quando foi planeado.
