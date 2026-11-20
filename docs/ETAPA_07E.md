# Etapa 7E — resultados científicos estruturados

Esta etapa define medições individuais e valida a sua correspondência ao protocolo.
O módulo é independente do harness: não executa experiências nem avalia ainda
os critérios científicos escritos em linguagem natural.

## Ordem de estudo

1. Lê `app/schemas/results.py`. `Measurement` guarda método, métrica, seed e
   valor numérico finito. Uma linha é uma observação por execução; não substituas
   as observações por uma média agregada das seeds.
2. `ExperimentResults` reúne as linhas, hash do protocolo, versões de código e
   dataset, parâmetros e origem `synthetic` ou `executed`. A origem é declarada
   pelo produtor dos dados: o campo não prova que uma experiência foi executada.
   Os parâmetros são uma string contendo um objeto JSON validado, preservando
   os seus campos. Esta versão não abre ficheiros nem executa os parâmetros.
3. Segue o validator: rejeita duplicados da combinação método/métrica/seed.
   O contrato rejeita NaN, infinito, booleanos como valores e strings numéricas.
4. Em `app/planning/result_validation.py`, observa o produto de métodos, métricas
   e seeds previsto pelo protocolo. A comparação de conjuntos identifica linhas
   em falta ou inesperadas. Os nomes das baselines devem corresponder exatamente
   aos do protocolo. O candidato tem nome explícito separado da descrição textual
   de `protocol.method`; a ligação semântica entre ambos ainda exige revisão.
5. O hash liga as medições à versão do protocolo. Uma mudança na regra de paragem,
   por exemplo, invalida essa ligação. O hash não verifica os dados nem a execução.
6. Executa `results_demo.py`. São seis valores inventados e identificados como
   sintéticos. `scientific_success` permanece `not_evaluated`, mesmo com estrutura
   válida. Não há afirmação de que a hipótese foi demonstrada.
7. Lê `tests/test_results.py` e altera uma seed no demo para observar a falha.

```powershell
.venv\Scripts\python.exe results_demo.py
.venv\Scripts\python.exe -m pytest tests/test_results.py -q
```

## Limites

O formato inicial exige todas as combinações previstas, sem execuções parciais
ou falhadas. Não calcula médias, intervalos de confiança ou significância.
Não valida unidades, fidelidade ao dataset, versões reais de código nem cumprimento
do orçamento experimental. A métrica do exemplo chama-se `mean_error`, mas os
valores guardados são por seed; a agregação entre seeds é uma etapa posterior.

O protocolo atual descreve critérios de sucesso em texto livre. Precisamos de
um contrato de critérios verificáveis antes de calcular aprovação científica.
Estes resultados não são inseridos no índice lexical nem convertidos em prosa.
Faltam persistência de execuções, leitores próprios e integração com o harness.
