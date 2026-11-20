# Etapa 4A — catálogo de modelos aprovados

Nesta etapa construímos o Model Registry. O MCP Registry continua para a etapa
seguinte. Mantivemos `openrouter/free` por tua escolha explícita; não acrescentámos
modelos pagos nem alterámos o teu ficheiro `.env`.

## 1. O catálogo é um ficheiro de dados

Começa por `config/model_registry.json`. Cada entrada declara:

- `provider` e `model`: identidade exata do serviço e do modelo.
- `enabled`: se está aprovado para uso.
- `is_router`: se pode escolher outro modelo por trás do nome pedido.
- `context_window` e `max_output_tokens`: contexto anunciado e limite local de geração.
- `tool_calling` e `structured_output`: capacidades necessárias para certas tarefas.
- `pricing`: preços por milhão de tokens, taxa por pedido, fonte e data da verificação.

O catálogo inicial só contém `openrouter/free`. Em 2026-09-26, a consulta pública
ao [catálogo da API](https://openrouter.ai/docs/api/api-reference/models/get-models)
confirmou contexto de 200000 tokens, preços de input/output a zero e suporte para
tools e structured outputs. A [página do router](https://openrouter.ai/openrouter/free/)
confirma esses preços e explica que o modelo escolhido pode variar.

O limite de output de 4096 é uma escolha local para limitar cada resposta; não é
uma afirmação sobre o máximo do fornecedor. Um resultado pode ficar truncado
se precisar de mais tokens. Não aumentamos esse limite automaticamente.

## 2. Validar ao carregar

Lê `app/registry/models.py`. `ModelRegistry.load(path)` lê JSON e usa Pydantic
para validar toda a estrutura antes de permitir chamadas. Rejeita preços
negativos/não finitos, limites inválidos e entradas repetidas por provider/model.
As entradas são imutáveis e o conjunto é uma tuple.

`ModelPricing` usa preços por milhão, sempre com `Decimal`:

```text
custo = taxa por pedido
      + (tokens de input × preço de input
         + tokens de output × preço de output) / 1 000 000
```

Os preços não são atualizados automaticamente pela internet. A validade local
inicial é 30 dias, configurável por entrada. Preços expirados ou com data futura
tornam a entrada inelegível. Quando expirar, confirma novamente as fontes antes
de atualizar preços/data; não basta mudar a data sem verificar.

## 3. Filtrar antes de decidir

`ModelRequirements` expressa os requisitos, e `candidates` devolve apenas entradas:

- ativas, com preços válidos;
- do provider pedido, quando especificado;
- com tools/structured output e contexto suficientes;
- dentro da reserva máxima pedida;
- com routers permitidos explicitamente nos requisitos.

`require` exige uma entrada exata entre os candidatos. Se não existir, recusa;
não escolhe silenciosamente outro modelo. Ainda não há JEV nem seleção automática
do modelo “melhor”. Há uma lista filtrada para um futuro decisor poder escolher.
Coding/reasoning scores, histórico de avaliações e latência ainda não são medidos.

## 4. Ligar aos clientes e ao planner

Lê `app/registry/runtime.py` e depois `app/models.py`. `get_model()` consulta o
catálogo antes de construir o cliente e passa o limite de output aprovado.
O planner recebe a lista de modelos elegíveis, e a escolha de runtime que devolve
no AgentSpec é novamente validada por código. Isto separa instruções de prompt
de verificação determinística.

Dentro de um build, o catálogo é carregado uma vez e guardado em
`.factory_runs/<build_id>/model_registry.json`. Alterar o ficheiro original
a meio do build não muda a versão usada. As chamadas verificam novamente a
validade temporal dos preços antes de reservar.

O callback guarda `model` pedido e `resolved_model` quando a resposta identifica
o modelo efetivo. Com `openrouter/free`, aprovamos o router, não cada modelo que
ele escolher. A [documentação do router](https://openrouter.ai/docs/guides/routing/routers/free-router)
descreve esse funcionamento. É uma exceção ao objetivo futuro de shortlist fixa.

## 5. Reserva automática e custo posterior

Antes da chamada, reservamos o custo de toda a janela como input, somado ao custo
do output máximo. É uma sobre-reserva deliberada que evita uma contagem incompleta
de prompts, histórico e schemas das ferramentas. Pode bloquear uma chamada que,
na prática, seria barata. Não é uma contagem exata dos tokens do pedido.

Depois da chamada:

1. Se existe custo reportado, usa-se esse valor.
2. Senão, se existem tokens de input e output, calcula-se uma estimativa pelo catálogo.
3. Sem ambos, continua desconhecido; uma falha também não é considerada gratuita.

Assim, já não é obrigatório fornecer uma reserva manual. Um override manual
maior é aceite; um menor não reduz a reserva calculada. Chamadas monitorizadas
recusam overrides de output acima do aprovado e inputs multimodais, porque esta
primeira tabela só representa preços simples de texto. O preço estimado não
modela escalões, descontos de cache, custos de ferramentas externas ou taxas
adicionais do fornecedor. Não adicionamos modelos com essas tabelas sem adaptar
o cálculo; o suporte atual não garante uma fatura máxima.

O limite de USD 1,00 por build continua ativo. Demos/clientes criados fora do
harness passam pela aprovação do catálogo, mas não têm um orçamento de build
ativo. Agentes gerados não ganham automaticamente esta política no seu runtime:
a integração da sessão de investigação continua planeada.

## 6. Estudar sem chamadas reais

```powershell
.\.venv\Scripts\python.exe model_registry_demo.py
.\.venv\Scripts\python.exe harness_offline_demo.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

O primeiro demo lê o catálogo e calcula também um preço fictício para ensinar
a fórmula. Esses preços fictícios não são guardados no catálogo real. O segundo
continua a usar um planner e builder falsos. Nenhum destes comandos precisa de
inferência real nos providers.

Ordem de estudo: JSON → models.py do registry → demo → runtime.py → app/models.py
→ callbacks.py. Lê depois `tests/test_model_registry.py` e
`tests/test_registry_integration.py`: incluem seleção recusada, preços expirados,
reservas, snapshots e clientes falsos com callbacks reais do LangChain.

As verificações desta etapa não chamaram modelos reais. Confirmam o nosso código
e a configuração dos clientes, não disponibilidade, qualidade ou sucesso de uma
geração ao vivo com o router.
