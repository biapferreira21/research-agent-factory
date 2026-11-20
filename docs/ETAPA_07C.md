# Etapa 7C — avaliar a recuperação antes de a expandir

Esta etapa acrescenta uma avaliação offline das fontes recuperadas. É independente
dos testes que o builder gera. Não chama modelos e não avalia validade científica.

## Ordem de estudo

1. Lê `examples/knowledge/retrieval_cases.json`. Cada caso tem uma pergunta,
   filtros opcionais e uma lista explícita de fontes esperadas. Uma lista vazia
   significa que esperamos não encontrar nada. Os rótulos são manuais.
2. Em `app/retrieval/evaluation.py`, lê `RetrievalCase`: Pydantic rejeita campos
   desconhecidos, nomes/perguntas vazios e fontes repetidas. `evaluate` rejeita
   suites vazias, nomes duplicados e fontes esperadas que não existem no índice.
   Um ficheiro vazio, sem trechos indexados, também não é uma fonte recuperável.
3. Segue a chamada a `RetrievalConfig.snapshot`. Avaliamos a mesma seleção usada
   pelo harness, depois dos filtros e do limite de caracteres, não apenas os
   resultados brutos da pesquisa.
4. Observa os conjuntos `expected` e `retrieved`. Vários trechos do mesmo ficheiro
   contam como uma fonte. A precisão é fontes corretas / fontes recuperadas.
   O recall é fontes corretas / fontes esperadas. Esta é uma avaliação por fonte,
   não por trecho, posição no ranking ou qualidade da resposta final.
5. Um denominador zero produz `null`. As médias excluem valores indefinidos e
   mostram isso no nome. Um caso passa só quando os conjuntos coincidem: nenhuma
   fonte esperada em falta nem fonte inesperada. `pass_rate` inclui casos negativos.
6. Executa `retrieval_eval_demo.py`: grava um relatório novo por execução com
   casos, métricas, omissões e snapshots completos das evidências selecionadas.
   O programa devolve exit code 1 se algum caso falhar; 0 se todos passarem.
7. Lê `tests/test_retrieval_evaluation.py`: verifica falhas conhecidas, contagem
   de fontes únicas, casos negativos e perda de evidências por limite de contexto.

```powershell
.venv\Scripts\python.exe retrieval_eval_demo.py
.venv\Scripts\python.exe -m pytest tests/test_retrieval_evaluation.py -q
```

Exercício: muda temporariamente `max_context_chars` no demo para 2 e volta a
executar. Os casos positivos devem falhar por não receberem evidência; os negativos
continuam a passar. Restaura depois o limite por omissão.

## Interpretar os resultados

Os cinco casos atuais são sintéticos e pequenos: servem para estudar o avaliador.
Um resultado de 5/5 não demonstra qualidade em investigação real. Para comparar
estratégias, precisamos de perguntas representativas e rótulos revistos por uma
pessoa que conheça o domínio. Os rótulos têm de enumerar todas as fontes relevantes
para que uma fonte não rotulada não seja penalizada indevidamente.

O relatório conserva hashes dos ficheiros recuperados e os trechos selecionados,
mas não uma cópia de todo o corpus. Para repetir uma avaliação com o mesmo corpus,
é necessário conservar as fontes e a configuração do índice (incluindo chunking).
Os relatórios podem conter texto privado das fontes, como os snapshots do harness.

Esta suite ainda não é um gate automático de cada build. Ainda faltam avaliações
das respostas/citações, experiências científicas estruturadas e seleção de
dimensões de avaliação. Não alterámos o orçamento nem ativámos JEV ou APIs pagas.
