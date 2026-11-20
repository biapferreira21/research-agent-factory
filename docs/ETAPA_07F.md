# Etapa 7F — critérios executáveis e comparação de resultados

Acrescentámos `executable_criteria` ao ResearchProtocol. O campo anterior
`success_criteria` continua a descrever a intenção em texto; não é interpretado
automaticamente. A correspondência entre texto e critérios requer revisão.

## Ordem de estudo

1. Em `app/schemas/research.py`, lê `SuccessCriterion`: métrica, baseline e
   melhoria relativa mínima. `0.05` significa 5%. O critério usa a média das
   seeds, comparando o candidato com a baseline nomeada. A direção vem da métrica.
2. O protocolo rejeita referências desconhecidas e critérios duplicados para o
   mesmo par métrica/baseline. A lista vazia mantém compatibilidade com protocolos
   que ainda não têm critérios verificáveis.
3. Em `app/planning/result_evaluation.py`, começa por `validate_results`: dados
   incompletos ou de outro protocolo não chegam à comparação.
4. Segue as somas de valores por método. Como os métodos têm as mesmas seeds,
   comparar as somas equivale a comparar as médias. A avaliação usa Decimal a
   partir da representação decimal das medições, evitando arredondar a divisão
   antes de decidir se o limiar foi atingido.
5. Para minimizar, melhoria = (baseline - candidato) / baseline. Para maximizar,
   melhoria = (candidato - baseline) / baseline. A baseline tem de ter média
   positiva. Zero ou valores negativos produzem `unsupported_baseline` e
   `criteria_met=null`; não escolhemos outra fórmula silenciosamente.
6. Todos os critérios têm de passar. Sem critérios, o estado é `not_evaluated`.
   Com dados sintéticos, é `synthetic_evaluation`, mesmo que os critérios passem.
   Com origem declarada `executed`, é `evaluated`; isto não autentica a execução.
7. Executa `result_evaluation_demo.py` e lê `tests/test_result_evaluation.py`:
   incluem igualdade ao limiar, falha, duas direções e alteração do protocolo.

```powershell
.venv\Scripts\python.exe result_evaluation_demo.py
.venv\Scripts\python.exe -m pytest tests/test_result_evaluation.py -q
```

## Limites e compatibilidade

Passar estes critérios é cumprir uma comparação aritmética pré-definida. Não é
significância estatística, demonstração da hipótese ou validação da experiência.
As versões, origem e medições continuam a ser declaradas pelo produtor dos dados.
O validador estrutural mantém `scientific_success=not_evaluated`; o avaliador
separado apresenta `criteria_met` sem afirmar sucesso científico geral.

Os critérios devem ser fixados antes das experiências e fazem parte do hash.
O novo campo, mesmo vazio, altera a serialização canónica usada no hash face a
versões antigas. Resultados guardados com hashes anteriores podem ser rejeitados;
não recalcules os hashes para disfarçar uma mudança de protocolo. Conserva os
artefactos antigos e trata a migração/versionamento explicitamente.

O módulo ainda é independente do harness. Não executa experiências nem chama APIs.
Faltam persistência, critérios absolutos, execuções parciais e análise estatística.
