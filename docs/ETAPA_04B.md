# Etapa 4B — biblioteca MCP, seleção e configuração

Esta etapa integra o CapabilityPlanner no harness e cria os contratos para MCPs.
Não instala servidores, não descobre ferramentas pela rede nem executa chamadas
MCP. O catálogo real começa vazio porque ainda não forneceste a tua biblioteca.
Não foram aprovados serviços fictícios no catálogo real.

## 1. Distinguir ferramentas locais de MCPs

Em `app/schemas/agent.py`, `ToolSpec` ganhou `source`, com duas opções:

```python
ToolSpec(name="read_file", description="Ler um ficheiro", source="local")
ToolSpec(name="literature_search", description="Pesquisar papers", source="mcp")
```

O default é `local`, mantendo a compatibilidade com os exemplos anteriores.
`RequiredCapabilitySpec` tem o mesmo campo. O nome de uma capacidade MCP é um
identificador do nosso catálogo, não uma descrição livre que o seletor interpreta.
O planeador tem de preservar os nomes e origens das ferramentas do AgentSpec.

## 2. Definir a biblioteca

Lê `app/registry/mcp.py`, começando por `MCPTool` e `RegisteredMCP`.
Cada servidor tem nome, versão, descrição, estado e ferramentas. Cada ferramenta
declara capacidades, permissões, domínios necessários, risco e custo estimado.

`status="approved"` representa aprovação administrativa no ficheiro. O programa
não determina sozinho se um servidor é confiável. Entradas draft/disabled não
podem ser selecionadas. `None` no custo significa desconhecido e impede a seleção;
zero tem de ser declarado explicitamente. Não há verificação automática de tarifas
MCP nesta etapa: a biblioteca é mantida por ti.

A autenticação opcional guarda apenas o nome de uma variável, como
`PAPERS_API_KEY`. Não coloca a credencial no JSON nem lê essa variável nesta etapa.
A configuração de transporte, endpoints, comandos e arranque do servidor ainda
não existe; pertencerá ao adaptador de runtime.

O ficheiro real é `config/mcp_registry.json`. Tem `servers: []` de propósito.
O exemplo fictício é criado apenas por `mcp_registry_demo.py`, sem ser instalado
ou copiado para esse ficheiro.

## 3. Separar pedidos de permissões

`CapabilitySpec` descreve necessidades. `MCPPolicy` descreve o que o harness
permite. O texto que um LLM coloca em `permissions` não altera esta política.

Por omissão, a política só permite risco baixo, custo zero e nenhuma permissão
ou domínio. Uma biblioteca real pode receber uma política explícita:

```python
policy = MCPPolicy(
    allowed_permissions=("network_read",),
    allowed_domains=("papers.example",),
)
```

Os identificadores e domínios são comparados exatamente. Não há expansão de
wildcards, resolução DNS ou validação de tráfego: não estamos a fazer chamadas.
São limites declarativos que um adaptador futuro terá de aplicar na execução.

Ferramentas pagas exigem simultaneamente `allow_paid=True` e um teto por chamada
suficiente. Nada nesta alteração autorizou APIs pagas na configuração real.
Este teto é distinto do orçamento de USD 1,00 dos modelos usados no build.

## 4. Selecionar só o necessário

Segue `MCPRegistry.select`:

1. Ignorar capacidades locais.
2. Procurar ferramentas que declarem a capacidade pedida.
3. Filtrar por aprovação, risco, permissões, domínios e custo.
4. Escolher por menor risco, número de permissões/domínios e custo; nomes e
   versões servem de desempate estável. Não se tenta adivinhar a versão mais recente.
5. Remover duplicados quando uma ferramenta cobre várias capacidades.
6. Bloquear se faltar uma capacidade obrigatória; registar opcionais indisponíveis.

`MCPSelection` guarda referências exatas a servidor, versão e ferramenta. Não dá
acesso a todas as ferramentas do servidor. Este seletor é determinístico: não é
JEV, não avalia qualidade científica e não resolve uma otimização global de cobertura.

`configure` volta a verificar as referências e a política antes de produzir
`MCPConfiguration`. Copia apenas as permissões/domínios necessários da ferramenta
selecionada, os limites de custo e a referência de credencial. Não aceita comandos
ou credenciais inventados por um LLM.

## 5. Validar o CapabilityPlanner

Em `app/planning/capability_validation.py`, comparamos AgentSpec e CapabilitySpec.
Recusamos nomes de agente diferentes, mudanças de memory/runtime, capacidades
duplicadas, omissão de ferramentas obrigatórias, troca da origem local/MCP e
pedidos MCP que não estavam no AgentSpec.

É uma validação estrutural; não prova que todas as descrições ou escolhas do
planeador fazem sentido científico. Essa avaliação é uma etapa futura.

## 6. Integrar no harness

O fluxo passa a ser:

```text
Planner → AgentSpec → CapabilityPlanner → validação → seleção/configuração MCP
        → preparação → Builder → gates → pytest
```

`BuilderHarness` aceita `capability_planner`, `mcp_registry` e `mcp_policy`
injetados. Em produção, usa o CapabilityPlanner com LLM. Nos testes e no demo
offline, recebe `offline_capability_planner`, sem chamadas externas. A chamada
real adicional ao planeador participa na telemetria e orçamento do build.

Nos builds locais, a pasta gerada recebe quatro contratos protegidos:

- `agent_spec.json`
- `capability_spec.json`
- `mcp_selection.json`
- `mcp_configuration.json`

As ferramentas do builder recusam escrever nesses ficheiros. O harness compara
o conteúdo antes e depois de pytest para detetar alterações persistentes.
Guarda também cópias dos contratos, catálogo e política em `.factory_runs/<id>`.
Essas cópias podem conter o objetivo e descrições do projeto; os eventos de
progresso continuam a não guardar prompts ou mensagens completas de exceções.

Se um MCP obrigatório não for encontrado, o build fica `blocked` antes da geração.
Se houver uma seleção válida com ferramentas MCP, guardamos os contratos nos logs
e também bloqueamos a geração, com indicação de que falta o adaptador de runtime.
Não geramos uma implementação fictícia para aparentar que existe uma ligação real.

Isto é uma limitação explícita desta etapa: já podemos validar a biblioteca e as
decisões; ainda não podemos entregar um agente que execute MCPs reais. Não há
medição ou reserva de custos de chamadas MCP porque essas chamadas não existem.

## 7. Estudar os exemplos

```powershell
.\.venv\Scripts\python.exe mcp_registry_demo.py
.\.venv\Scripts\python.exe harness_offline_demo.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

O primeiro usa um servidor fictício com `search` e `delete`. Só seleciona `search`.
O segundo continua a gerar e testar uma função local, agora com a etapa de capacidades.

Ordem de leitura: catálogo vazio → classes em registry/mcp.py → demo →
capability_validation.py → harness.py → testes test_mcp_registry.py e test_mcp_harness.py.

Exercício: no demo, remove `network_read` da política e observa o bloqueio.
Depois torna `literature_search` opcional e observa `omitted_optional`.

Próximos passos: ResearchPlanner/Scientific Agent Architect para ligar os contratos
científicos à criação do agente; e, quando existir uma biblioteca concreta aprovada,
um adaptador MCP com ligação, autenticação, execução e controlo de custos.
