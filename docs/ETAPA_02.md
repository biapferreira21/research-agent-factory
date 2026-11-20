# Etapa 2 — estudar o controlo do harness

## 1. Criar quando é necessário

Começa por `app/builder/agent.py`. Antes, `builder_agent = create_agent(...)`
corria logo ao importar o ficheiro. Agora `create_builder_agent(workspace)`
só cria o agente quando é chamada. O planner e o capability planner seguem a
mesma regra. Importar o harness já não chama `get_model()`.

Uma factory é apenas uma função que cria um objeto. Não é um novo framework.
O planner também passou a indicar o modelo do provider configurado no pedido,
em vez de indicar sempre o nome do modelo OpenAI.

## 2. Guardar a pasta nas ferramentas

Em `app/tools/filesystem.py`, lê `resolve_workspace_path` e depois
`create_filesystem_tools`. Esta última devolve três ferramentas novas para cada
build. As funções interiores lembram-se da variável `root`: isto é uma closure.
Assim, dois builders podem ter raízes diferentes sem mudar uma variável global.

Os caminhos são relativos à pasta do build: escreve `agent.py`, não o caminho
completo em generated_agents. O código resolve o caminho e confirma que continua
dentro da raiz. Recusa caminhos absolutos, escapes para pastas superiores e
algumas ambiguidades do Windows, incluindo streams alternativos e pontos/espaços
finais. A ferramenta de escrita recusa alterar `agent_spec.json`.

Estas verificações limitam as ferramentas de ficheiros; não são uma sandbox do
sistema operativo nem protegem contra outro processo que altere os ficheiros.

## 3. Separar execução e apresentação dos testes

Em `app/tools/testing.py`, `PytestResult` é uma dataclass: agrupa código de saída,
log e indicação de timeout. `passed` é uma propriedade calculada. `as_text()`
serve para apresentar o resultado; o harness decide com `passed`, sem interpretar
um prefixo de texto. `execute_pytest` executa dentro da pasta gerada e limita o
tamanho do log. Um timeout nunca é sucesso.

## 4. Injetar dependências

Em `app/builder/harness.py`, lê o construtor antes de `build`:

```python
harness = BuilderHarness(
    planner=offline_planner,
    builder_factory=OfflineBuilder,
)
```

Passamos funções/classes, sem as executar aqui. Mais tarde, `build` chama o
planner, cria o builder com a pasta autorizada e pede-lhe que trabalhe.
Os valores por omissão continuam a usar os modelos reais.

`Callable` descreve a assinatura esperada de uma função. `Protocol` descreve o
método `invoke` que o harness espera num builder; não se deve confundir com o
`ResearchProtocol` científico da etapa 1. O builder falso não precisa de herdar
explicitamente desse Protocol para ter o método necessário.

O fluxo é: validar pedido → obter e revalidar AgentSpec → criar pasta → guardar
contrato → criar builder → gerar ficheiros → verificar contrato → gates → pytest
→ verificar contrato novamente → devolver BuildResult.

Erros de validação do pedido e exceções de providers continuam a propagar-se.
Ainda não há eventos persistentes, recuperação automática nem repair loop.

## 5. Executar o exemplo sem APIs

Lê `harness_offline_demo.py`. O planner devolve um contrato fixo, e o builder
escreve uma função de saudação e um teste através das mesmas ferramentas limitadas
que um builder real usaria. O harness executa gates e pytest reais.

```powershell
.\.venv\Scripts\python.exe harness_offline_demo.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

Cada execução do demo deixa uma nova pasta com UUID em generated_agents/offline_demo.
Este exemplo valida o funcionamento do harness; não é um agente científico nem
um substituto determinístico para o agente com LLM que construiremos depois.

## 6. Ler os testes como experiências

- `tests/test_harness.py`: build offline completo, falhas, gates e adulteração do contrato.
- `tests/test_scoped_tools.py`: dois builds independentes, caminhos recusados e contrato protegido.
- `tests/test_testing_tool.py`: sucesso, falha, timeout e logs longos.
- `tests/test_lazy_agents.py`: importação num processo novo sem construir modelos.

Exercício: no teste do projeto criado pelo demo, muda a resposta esperada de
`Hello, Ada!` para `Hello, Bob!` e executa pytest nessa pasta. Depois observa a
diferença entre falha de um teste e erro de sintaxe detetado pelos gates.

A etapa seguinte é telemetria e orçamento: eventos de progresso, tokens,
durações e custos. O limite de despesa e a ação ao atingi-lo ainda precisam de
ser definidos antes de impor uma política de orçamento real.
