# Agent Factory: roteiro de implementação e estudo

## Ponto de partida

O código atual implementa Planner → AgentSpec → Builder → gates → pytest.
O CapabilityPlanner já participa no BuilderHarness, antes da geração de código.
O plano fornecido acrescenta investigação científica antes da geração de código,
registos aprovados, decisões tipadas, custos e proveniência.

Vamos evoluir por etapas estudáveis. As etapas 1 e 2 estão implementadas, assim
como a base da etapa 3 (eventos, custos e reservas integrados no harness).
O Model Registry da etapa 4 também está implementado.
O MCP Registry, a seleção e configuração declarativas também estão implementados;
a execução de MCPs reais continua pendente.
O caminho científico da etapa 5 também está integrado através de `build_research`.
O serviço de decisões tipadas da etapa 6 está integrado no routing de criação dos
clientes; usa regras locais por omissão. O adaptador HTTP JEV está implementado
e testado com HTTP simulado; validação com o serviço real continua pendente.
O exemplo científico é manual e offline; não gera um agente nem executa
experiências. O novo exemplo do harness gera um pequeno projeto determinístico
para testar a infraestrutura. Validação de estrutura não demonstra validade científica.

## 1. Contratos científicos — implementado

Ordem de leitura:

1. `app/schemas/research.py`: define o formato da pergunta e do protocolo.
2. `research_demo.py`: constrói uma pergunta e usa-a num protocolo completo.
3. `tests/test_research_schema.py`: mostra exemplos que devem ser rejeitados.

Conceitos Python/Pydantic para estudar:

- `class`: agrupa campos e comportamento num tipo reutilizável.
- Herança de `ResearchContract`: partilha a configuração de validação.
- `list[str]`: declara uma lista de textos; Pydantic valida os dados recebidos.
- `Literal`: restringe as opções, como minimizar ou maximizar uma métrica.
- `Field(min_length=1)`: impede texto ou listas vazias.
- `default_factory=list`: cria uma lista nova para cada instância.
- `model_validator`: verifica relações entre campos, como métricas duplicadas.
- `model_dump_json`: serializa o contrato para o guardar ou enviar a um modelo.
- `if __name__ == "__main__"`: executa o exemplo apenas quando lançado diretamente.

Executar na raiz, em PowerShell:

```powershell
.\.venv\Scripts\python.exe research_demo.py
.\.venv\Scripts\python.exe -m pytest tests/test_research_schema.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

Exercício: repetir uma seed, apagar as baselines ou trocar `minimize` por outro
texto e observar o ValidationError. A hipótese é uma previsão; não é um resultado.
O protocolo define antecipadamente como medir, comparar e parar.

## 2. Tornar o harness testável e reforçar os limites — implementado

Os agentes são agora criados apenas ao executar, em vez de durante imports.
O harness aceita planners, builders e test runners falsos. O nome do agente é
validado antes de criar caminhos. As ferramentas entregues ao builder ficam
limitadas à pasta desse build e recusam escrita em agent_spec.json. As ferramentas
globais antigas continuam disponíveis para compatibilidade, mas não são dadas ao builder.

O builder escreve os testes; o harness executa-os. O resultado do pytest guarda
o código de saída separado do log, mesmo quando este é truncado, e executa na
pasta do projeto. O harness verifica também se o contrato foi alterado, antes e
depois da validação. Isto deteta alterações persistentes, não impede que código
Python arbitrário aceda ao sistema. O pytest continua a executar como processo
local, sem sandbox de execução. Isolamento de processos fica para uma etapa própria.

Lê `docs/ETAPA_02.md` para acompanhar as alterações ficheiro a ficheiro.

```powershell
.\.venv\Scripts\python.exe harness_offline_demo.py
```

O demo não chama modelos e cria um build novo em generated_agents/offline_demo.
Os demos antigos foram adaptados à factory e continuam a fazer chamadas reais a
modelos quando executados; não são o exercício offline desta etapa.

## 3. Telemetria e orçamento — base implementada

BuildStage, BuildEvent, UsageRecord e CostTracker estão implementados. O harness
mostra progresso, guarda logs fora da pasta do builder e monitoriza chamadas
feitas pelos modelos de get_model(). O limite escolhido é USD 1,00 por build.
O Model Registry calcula agora reservas e impõe limites de output. Sem custo
reportado, estima pelos tokens; sem ambos, bloqueia a próxima chamada. Reservas
não garantem uma fatura máxima. Retries internos estão desativados nos builds monitorizados.

Faltam tabelas de preços complexas, orçamento de sessão de investigação,
custos de MCPs e recuperação após interrupção. Lê `docs/ETAPA_03.md` e executa
`budget_demo.py` e `harness_offline_demo.py` para estudar sem APIs.

## 4. Registos aprovados — catálogos e seleção implementados

O ModelRegistry é carregado de JSON validado, filtra por capacidades/contexto/custo,
verifica aprovação e validade dos preços e é guardado com cada build real.
openrouter/free foi mantido por escolha explícita como exceção de router. Não há
modelos pagos aprovados no catálogo inicial. Lê `docs/ETAPA_04.md` e executa
`model_registry_demo.py` para estudar.

O MCPRegistry separa biblioteca, seleção por agente e configuração. Filtra por
aprovação, capacidades, risco, permissões, domínios e custo. O catálogo real começa
vazio. O CapabilityPlanner está integrado com validação determinística e contratos
protegidos. Lê `docs/ETAPA_04B.md` e executa `mcp_registry_demo.py`.

Falta o adaptador de runtime: builds com MCPs selecionados ficam bloqueados após
guardar os contratos, em vez de gerar integrações fictícias. Para ligar MCPs reais,
precisamos da biblioteca aprovada e de implementar transporte/autenticação/execução.

## 5. ResearchPlanner e Scientific Agent Architect — integrados

`build_research` transforma a pergunta em ResearchQuestionSpec e ResearchProtocol
e entrega o protocolo ao Scientific Agent Architect para produzir o AgentSpec.
As etapas partilham o orçamento do build. Informação essencial em falta ou
alterações à pergunta bloqueiam a geração. Os contratos ficam protegidos e o
AgentSpec contém um hash do protocolo usado.

Lê `docs/ETAPA_05.md` e executa `research_harness_demo.py`. A validação foi offline,
com respostas falsas e pytest real; não foram executadas experiências ou chamadas
de investigação reais. Validação estrutural e hash não comprovam qualidade científica.

## 6. Serviço de decisões — base e adaptador HTTP JEV implementados

Existem contratos de estado, candidatos, decisão, confiança e probabilidades.
O serviço rejeita escolhas fora dos candidatos e regista as tentativas. Por omissão,
preserva o modelo configurado; confiança inferior a 0,80 bloqueia. Fallback é
opcional e explícito, com os mesmos candidatos e validações. O routing filtra
modelos por capacidades/preços/orçamento antes de consultar o decisor.

Lê `docs/ETAPA_06.md` e `docs/ETAPA_06B.md`. Executa `decision_demo.py` e
`jev_offline_demo.py`. O adaptador HTTP JEV tem reserva de custos, timeout,
validação e testes com HTTP simulado. A ativação é explícita por injeção no
harness; ainda não foi validado com chamadas reais. Faltam decisões para
MCPs/RAG/avaliações. JEV selecionará alternativas; o LLM generativo escreverá
casos de avaliação.

## 7. RAG, capacidades e avaliações científicas

A etapa 7A implementa recuperação lexical local independente do harness, com
fontes globais/de domínio/de projeto, filtros e proveniência por linhas/hash.
Lê `docs/ETAPA_07A.md` e executa `retrieval_demo.py`. A integração de evidências
no contexto dos planners e a fotografia por build estão implementadas na
etapa 7B, opcional através de `RetrievalConfig`. Lê
`docs/ETAPA_07B.md`: o harness guarda os trechos selecionados e fornece contexto
limitado aos planners, mantendo o pedido original.

A etapa 7C acrescenta avaliação offline por conjuntos de fontes esperadas,
depois dos filtros e do limite de contexto. Lê `docs/ETAPA_07C.md` e executa
`retrieval_eval_demo.py`. Os cinco casos sintéticos são didáticos; ainda não
constituem avaliação científica. A etapa 7D integra um gate opcional no build:
`retrieval_cases` exige aprovação de todos os casos antes dos planners e guarda
o relatório. Lê `docs/ETAPA_07D.md`; nenhuma suite é ativada por omissão.

A etapa 7E define medições por método/métrica/seed, proveniência declarada e
validação estrutural contra o protocolo. Lê `docs/ETAPA_07E.md` e executa
`results_demo.py`. Os valores do demo são sintéticos; o módulo ainda não executa
experiências, não avalia sucesso científico e não está integrado no harness.

A etapa 7F acrescenta critérios executáveis opcionais ao protocolo e um avaliador
de melhoria relativa média face às baselines. Lê `docs/ETAPA_07F.md` e executa
`result_evaluation_demo.py`. Cumprimento aritmético não comprova significância
ou validade científica; os exemplos continuam identificados como sintéticos.

A etapa 7G guarda protocolo, medições e avaliação num arquivo por UUID, com
manifesto de hashes e recálculo ao reler. Lê `docs/ETAPA_07G.md` e executa
`result_store_demo.py`. É persistência de avaliações, não execução experimental
nem reprodução do dataset/código; a integração com builds continua pendente.

A etapa 7H acrescenta associação explícita de medições a builds científicos
concluídos: verifica eventos e hashes, preserva contratos e arquiva a avaliação
com `source_build_id`. Lê `docs/ETAPA_07H.md`. A execução experimental permanece
pendente; associar resultados não prova que foram produzidos pelo agente.

Separar conhecimento global, domínio e projeto. Começar com fontes locais e
proveniência; adicionar estratégias lexical/vector/hybrid gradualmente. Resultados
estruturados de experiências devem manter estrutura. O CapabilityPlanner já usa
validação e seleção no harness. Selecionar dimensões de avaliação e gerar casos concretos,
com validação determinística independente dos testes escritos pelo builder.

## 8. Integração e repair loop

A etapa 8A implementa reparação opcional de falhas de gates/testes, limitada
por tentativas e pelo orçamento do build. Contratos alterados, timeouts e
erros de infraestrutura não são repetidos. Lê `docs/ETAPA_08A.md`.

A etapa 8B permite um `acceptance_validator` externo à pasta gerada, executado
após pytest e repetido após reparações. Guarda resultados em `acceptance.jsonl`.
Lê `docs/ETAPA_08B.md`; verificações de comportamento específicas ainda precisam
de ser fornecidas pelo chamador e não há isolamento automático deste hook.

A etapa 8C acrescenta `PythonAcceptance`: script externo em processo separado,
timeout e resposta JSON validada. Lê `docs/ETAPA_08C.md`. É separação de processo,
não sandbox; os verificadores precisam de ser de confiança.

A etapa 8D acrescenta metadados do verificador em cada registo de aceitação,
incluindo hash esperado, timeout e Python, e regista falhas de execução sem
mensagens brutas de exceções. Lê `docs/ETAPA_08D.md`.

A etapa 8E acrescenta `build_report.py UUID`: consulta estado, custos do último
evento, reparações, aceitação e avaliações associadas verificáveis. Lê
`docs/ETAPA_08E.md`. É leitura local, sem retomar ou executar o build.

A etapa 8F acrescenta `build_report.py --list`, com paginação e indicação de
builds ilegíveis sem ocultar os restantes. Lê `docs/ETAPA_08F.md`.

A etapa 8G guarda `build_result.json` por build novo, com estado final, caminhos,
custos, erros e contagem de reparações. Lê `docs/ETAPA_08G.md`. A publicação usa
um temporário, mas não constitui checkpoint nem retoma de execução.

Ligar o pipeline completo ao BuilderHarness, mostrar progresso no terminal,
persistir eventos/resultados e retomar reparações com limite de tentativas e custo.
Separar falhas de código, de infraestrutura e de validade científica.

## Decisões ainda em aberto no plano fornecido

O budget de build ficou definido em USD 1,00; novas chamadas são bloqueadas se não
couberem no saldo ou existir custo desconhecido. O catálogo inicial aprova apenas
openrouter/free como exceção. Faltam orçamento de investigação,
shortlist de modelos individuais, eventual fallback por LLM, armazenamento RAG, APIs pagas nos
MCPs e preferência de interface. Devem ser fechados antes das integrações correspondentes.
