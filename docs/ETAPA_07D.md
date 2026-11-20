# Etapa 7D — gate de recuperação antes dos planners

O harness aceita `retrieval_cases` em conjunto com `retrieval`. Se fornecidos,
todos os casos têm de passar antes do planeamento geral ou científico. Sem casos,
o fluxo mantém-se: recuperação opcional sem avaliação automática.

## Ordem de estudo

1. Em `app/builder/harness.py`, procura `retrieval_cases` no construtor. Os casos
   são copiados e validados. Uma suite vazia, nomes repetidos ou casos sem uma
   configuração de recuperação são erros de configuração.
2. Segue a etapa `RETRIEVAL_EVALUATION`. Executa o avaliador da etapa 7C usando
   o mesmo índice, limite de resultados e limite de caracteres do build.
3. Observa a escrita de `retrieval_evaluation.json`, fora da pasta do builder,
   antes de decidir se o build pode prosseguir. Uma fonte esperada inexistente
   produz `invalid_suite` e guarda os casos para diagnóstico.
4. Lê `app/retrieval/errors.py`: `RetrievalBlocked` identifica este bloqueio.
   O harness devolve `status="blocked"`, sem criar workspace nem chamar planners.
   A telemetria também regista a etapa como bloqueada.
5. Lê `tests/test_retrieval_gate.py`: cobre passagem, bloqueio nos dois caminhos,
   limite de contexto insuficiente, suite inválida e ausência de chamadas a modelos.

## Exemplo de configuração

Depois de criar o `index` e os casos como no demo da etapa 7C:

```python
from app.builder.harness import BuilderHarness
from app.retrieval.context import RetrievalConfig
from app.retrieval.evaluation import RetrievalCase

cases = (RetrievalCase(name="baseline", query="baseline",
                       expected_sources=("global.md",)),)
harness = BuilderHarness(
    retrieval=RetrievalConfig(index),
    retrieval_cases=cases,
)
# harness.build("Criar um agente para comparar uma baseline")
```

O exemplo pressupõe `global.md` no índice e que seja a única fonte global que
corresponde à consulta. `build` usa modelos reais por omissão; para experimentar
offline executa os testes:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_retrieval_gate.py -q
```

Os filtros domínio/projeto pertencem a cada caso. Não são substituídos pelos do
build, permitindo testar vários scopes na mesma suite. Escolhe casos que cubram
o domínio e projeto usados: passar noutro domínio não certifica o pedido atual.

O gate verifica a suite configurada, não a resposta do modelo nem cada pedido
possível. Os exemplos sintéticos não são ativados por omissão. Uma suite fraca
pode passar com um sistema inadequado; os rótulos continuam a exigir revisão.
Não se acrescentaram chamadas pagas nem alterações ao orçamento de USD 1,00.
