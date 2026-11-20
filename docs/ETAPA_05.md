# Etapa 5 — pergunta científica, protocolo e desenho do agente

O novo método `BuilderHarness.build_research(...)` liga os contratos científicos
da etapa 1 ao pipeline de construção. `build(...)` continua a servir pedidos
gerais. Esta etapa não executa investigação real nem demonstra que uma hipótese
é verdadeira: constrói o plano e o agente que deverá respeitá-lo.

## 1. Formalizar a pergunta

Lê `app/planning/research_planner.py`, começando por `formalize_research_question`.
A função cria um agente apenas quando é chamada, pede uma resposta estruturada
e valida-a como `ResearchQuestionSpec`.

Além dos campos anteriores, a pergunta e o protocolo têm agora:

- `assumptions`: propostas ou pressupostos que não vieram explicitamente do pedido.
- `open_questions`: informação essencial ainda por esclarecer.

Os prompts mandam distinguir uma hipótese de um resultado observado. Também
mandam assinalar dados em falta e não inventar fontes, datasets ou medições.
Estas instruções orientam o modelo; não provam que uma resposta seja cientificamente
correta ou fiel ao pedido. O pedido original é guardado para permitir comparação.

Se já tiveres um `ResearchQuestionSpec`, podes passá-lo diretamente a
`build_research`. Nesse caso, o harness valida o contrato e dispensa a chamada de
formalização. Uma pergunta com `open_questions` bloqueia antes do ResearchPlanner.

## 2. Definir como testar a hipótese

Segue `create_research_protocol`. Recebe a pergunta e devolve um `ResearchProtocol`
com método, baselines, métricas, seeds, critérios de sucesso, regra de paragem,
proveniência, limitações e pressupostos.

O protocolo tem de preservar exatamente o objeto da pergunta recebido. O código
recusa mudanças na hipótese, inputs, restrições ou restantes campos. Também bloqueia
se o protocolo indicar questões essenciais em aberto. Esta verificação acontece
antes de pedir a implementação do agente.

O schema inicial continua orientado a experiências comparativas. Uma revisão
puramente teórica ou outro desenho científico pode precisar de outro contrato.
O prompt pede para assinalar incompatibilidades em `open_questions`; não pretendemos
que todos os tipos de investigação caibam neste formato.

## 3. Desenhar o agente a partir do protocolo

Lê `app/planning/scientific_architect.py`. O Scientific Agent Architect reutiliza
o architect base, mas recebe o protocolo completo e instruções científicas em
`research_prompt.py`. A escolha do modelo de runtime continua sujeita ao catálogo.

O protocolo é enviado com as baselines, métricas, seeds, paragem e proveniência,
para orientar ferramentas, comportamento e avaliações do AgentSpec. O harness
recusa um AgentSpec científico sem avaliações explícitas. A presença de avaliações
não garante a sua qualidade: ainda faltam os evals científicos independentes.

O papel de architect não implica automaticamente um modelo mais forte. Por agora
usa o modelo configurado, tal como os outros papéis; o routing vem noutra etapa.

## 4. Associar o agente à versão do protocolo

Em `app/planning/research_validation.py`, `protocol_digest` serializa o protocolo
com chaves ordenadas e calcula SHA-256. O harness escreve o valor em
`AgentSpec.research_protocol_sha256` depois de validar o protocolo.

Um hash é aqui um identificador do conteúdo. A mesma estrutura JSON produz o
mesmo identificador, mesmo com indentação diferente; alterar uma seed muda-o.
O LLM não decide esse identificador. O hash não prova validade científica nem
que a implementação realmente cumpre o protocolo.

Passamos cópias profundas da pergunta e do protocolo às dependências. Assim, um
planner/architect injetado não modifica os contratos originais por partilha de
referências Python. `model_copy(deep=True)` copia também os objetos interiores.

## 5. Acompanhar o harness

Em `app/builder/harness.py`, lê `build_research` → `_plan_research` → `_build`:

```text
request
  → research_question
  → research_protocol
  → scientific_architect
  → capabilities
  → preparing
  → generating
  → gates
  → tests
```

Usamos o mesmo `BuildTelemetry` e `CostTracker` ao longo deste fluxo. Todas as
chamadas a modelos feitas via `get_model()` participam no limite de USD 1,00 por
build. Esse limite não é um orçamento para as experiências futuras.

Nos builds concluídos, o projeto recebe mais três contratos protegidos:

- `research_request.json`: texto do pedido original; se recebemos um contrato pronto,
  guarda o texto da pergunta desse contrato.
- `research_question.json`: pergunta formalizada completa.
- `research_protocol.json`: desenho experimental.

As ferramentas do builder não podem alterá-los. O harness também compara o
conteúdo antes e depois de pytest. Os artefactos de planeamento completados são
guardados nos logs durante o processo, para não depender de a geração terminar.
Respostas rejeitadas dentro de uma função de planeamento podem não produzir um
artefacto de protocolo; a falha e o seu tipo ficam nos eventos.

O novo caminho mantém os bloqueios anteriores: por exemplo, um protocolo cujo
agente exige MCPs reais ainda encontrará o bloqueio da biblioteca/adaptador MCP.

## 6. Executar o exemplo offline

```powershell
.\.venv\Scripts\python.exe research_harness_demo.py
```

Lê o demo pela mesma ordem do pipeline:

1. `offline_question_formalizer`: conhece apenas a pergunta A/B do exemplo.
2. `offline_research_planner`: usa o protocolo didático, preservando a pergunta.
3. `offline_scientific_architect`: desenha um programa que apresenta o plano.
4. `OfflineResearchBuilder`: escreve um pequeno programa e um teste de conformidade.
5. O harness executa gates e pytest reais sobre esse programa.

O programa gerado lê `research_protocol.json`, apresenta métricas e execuções de
baseline por seed e devolve `planned_not_executed`. Não otimiza um modelo, não
mede erro e não declara sucesso da hipótese. Os dados do demo são fixos e não
representam interpretação de perguntas arbitrárias.

O comando mostra a pasta do projeto e dos logs. Experimenta abrir os contratos
e comparar `research_protocol_sha256` no AgentSpec. Evita alterar os contratos
de um build existente; para estudar outra pergunta, cria um novo build.

## 7. Usar os modelos reais mais tarde

Depois de configurar o catálogo e as credenciais, a API de utilização é:

```python
from app.builder.harness import BuilderHarness

# Esta variante pode chamar modelos reais, ao contrário do demo offline.
result = BuilderHarness().build_research("A minha pergunta científica...")
```

Não executámos essa variante nesta etapa. Os testes usam planners e builders
falsos; verificam o encadeamento, os contratos, os bloqueios, o hash e a execução
local de pytest. Não avaliam a qualidade de respostas reais do router.

Os testes novos estão em `tests/test_research_planning.py` e
`tests/test_research_harness.py`. Para verificar toda a Factory:

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Ordem de estudo: research_prompt.py → research_planner.py → research_validation.py
→ scientific_architect.py → `_plan_research` no harness → research_harness_demo.py.

Próxima etapa do roteiro: contrato de decisões tipadas e fallback, começando com
um decisor falso antes de ligar o JEV real. RAG, execução de experiências e evals
científicos independentes continuam planeados.
