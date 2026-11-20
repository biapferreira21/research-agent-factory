# Etapa 8A — ciclo de reparação limitado

O BuilderHarness aceita agora `max_repair_attempts`, entre 0 e 5. O valor por
omissão é 0 para preservar o comportamento anterior e evitar novas chamadas
automáticas sem uma configuração explícita. O campo antigo homónimo em Settings
não ativa este ciclo; passa o valor ao construtor do harness.

## Ordem de estudo

1. Em `app/builder/harness.py`, lê `BuildValidationFailed.repairable`.
   Violações dos contratos não são reparáveis automaticamente.
2. Segue `_validate_build`: gates podem desencadear reparação; pytest com código
   1 (falha de testes) ou 5 (sem testes) também. Timeout e códigos 2/3/4 param.
   Isto é uma classificação conservadora por código, não diagnóstico completo.
3. Depois da geração, o `while` valida o projeto. Cada falha guarda um ficheiro
   `validation_N.json` na telemetria, incluindo os diagnósticos disponíveis.
4. Se houver tentativas disponíveis, cria um builder na mesma pasta e transmite
   contratos/pedido original e até 16000 caracteres de diagnóstico. Os logs são
   tratados no prompt como dados não fiáveis. O modelo deve corrigir a implementação
   preservando contratos e exigências dos testes.
5. Após cada reparação, repete gates e pytest. A saída `repair_attempts` conta
   tentativas iniciadas; pode incluir uma tentativa que depois falhou ou foi
   bloqueada ao construir/chamar o modelo. Não é o número de chamadas ao modelo.
6. Lê `tests/test_repair_loop.py`: cobre sucesso após reparação, limite esgotado,
   falhas de infraestrutura e alteração de contratos.

```python
from app.builder.harness import BuilderHarness
harness = BuilderHarness(max_repair_attempts=2)
# harness.build("O teu pedido")  # usa modelos reais por omissão
```

```powershell
.venv\Scripts\python.exe -m pytest tests/test_repair_loop.py -q
```

## Custos e limites

Não há novo orçamento: as chamadas de reparação usam o mesmo contexto de build,
catálogo, reservas e limite de USD 1,00. Custos desconhecidos/excedidos param antes
da tentativa; a reserva do modelo verifica se cada chamada cabe no saldo.

Um prompt que manda preservar testes não impede um modelo de os enfraquecer.
Os testes ainda são gerados/editados pelo builder; falta uma suite independente
de aceitação do agente. Os contratos continuam protegidos pelas ferramentas e
comparados antes/depois dos testes. Isto não é isolamento do sistema operativo.

Os diagnósticos podem conter texto produzido pelos testes e ficam na telemetria;
quando a reparação está ativa, parte desse texto é enviada ao modelo configurado.
Não executar testes com segredos em outputs. Não há retomada após interrupção,
rollback, nem reparação automática de experiências ou hipóteses científicas.
