# Etapa 7B — evidências no harness

O harness aceita agora `retrieval=RetrievalConfig(...)`. Antes do planeamento,
pesquisa usando o pedido original e guarda `retrieval_snapshot.json` na pasta
de telemetria do build. A seleção é feita uma vez e partilhada pelo planner
geral, formalizador da pergunta, planner científico e architect científico.
O CapabilityPlanner e o builder não recebem diretamente estes trechos.

## Ordem de estudo

1. `app/retrieval/context.py`: `RetrievalConfig` configura domínio, projeto,
   número de resultados e limite de caracteres. `snapshot` inclui apenas trechos
   inteiros cujo JSON, incluindo metadados, cabe no limite de 12000 caracteres.
   Um trecho grande é omitido e a procura continua pelos restantes resultados.
   A seleção considera os primeiros `limit` resultados; não procura substitutos
   além desse conjunto. `skipped_for_size` torna essas omissões visíveis.
2. `app/builder/harness.py`: observa a nova etapa `RETRIEVAL` antes dos planners.
   A fotografia contém consulta, filtros, evidências e o JSON entregue ao modelo.
   É guardada antes de invocar o planner, inclusive se este falhar depois.
3. `app/telemetry/build.py`: `retrieval_context` pertence ao build ativo. O
   ContextVar já existente restaura o contexto ao sair, incluindo em erros.
4. `evidence_messages`: acrescenta uma regra de sistema e uma mensagem de dados
   antes do pedido original. O conteúdo recuperado não pode substituir instruções
   ou alterar a pergunta. Esta regra de prompt não garante resistência a injeções.
5. `app/builder/planner.py` e `app/planning/research_planner.py`: observam o
   contexto automaticamente. O architect científico reutiliza o planner geral.
   Planners personalizados injetados pelo chamador precisam de usar
   `evidence_messages()` se quiserem consumir as evidências.
6. `tests/test_retrieval_context.py`: exemplos offline verificam limites,
   persistência, conteúdo recebido e limpeza do contexto após falhas.

## Configurar explicitamente

```python
from pathlib import Path
from app.builder.harness import BuilderHarness
from app.retrieval.local import LocalIndex, Source
from app.retrieval.context import RetrievalConfig

index = LocalIndex(Path("examples/knowledge"), [
    Source(path="global.md", scope="global"),
    Source(path="statistics.md", scope="domain", domain="statistics"),
])
harness = BuilderHarness(retrieval=RetrievalConfig(index, domain="statistics"))
# harness.build("Criar um agente que compare uma baseline")
```

Executar `build` com os planners por omissão faz chamadas reais aos modelos.
Para estudar sem rede, executa os testes:

```powershell
.venv\Scripts\python.exe -m pytest tests/test_retrieval_context.py -q
```

Sem `retrieval`, o comportamento mantém-se. Os filtros são explícitos: não são
inferidos do texto ou escolhidos pelo JEV. O índice conserva o conteúdo lido na
sua criação; reconstrói-o para incorporar edições às fontes.

O limite cobre apenas o JSON das evidências, não o prompt completo nem tokens.
Esses textos aumentam os tokens dos planners, cujas chamadas continuam no
orçamento do build. A pesquisa local não faz chamadas pagas.

A fotografia guarda os trechos selecionados, não os ficheiros completos. O hash
identifica o ficheiro original. Estes registos podem conter dados das fontes e
devem ter o mesmo controlo de acesso. Ficam fora das ferramentas do builder,
mas isso não constitui uma sandbox de execução.

Ainda faltam avaliações da qualidade da recuperação, validação das citações
geradas, leitores de resultados estruturados e estratégias vetoriais/híbridas.
