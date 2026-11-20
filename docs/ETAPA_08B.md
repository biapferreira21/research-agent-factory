# Etapa 8B — aceitação independente do builder

O harness aceita `acceptance_validator`, uma função de confiança fornecida pelo
chamador e mantida fora da pasta gerada. Corre depois dos gates e do pytest.
Devolve `[]` se aprovar ou uma lista de mensagens de erro se reprovar.

## Ordem de estudo

1. Procura `acceptance_validator` em `app/builder/harness.py`. A função recebe
   apenas o caminho do workspace. O builder não recebe o código do validador.
2. Em `_validate_build`, segue a etapa `ACCEPTANCE`. Mesmo que os testes gerados
   passem, erros de aceitação fazem falhar a validação.
3. Cada resultado é acrescentado a `acceptance.jsonl`, fora do workspace. Os
   contratos voltam a ser verificados depois de executar o validador.
4. Se a função devolver erros, pode desencadear uma reparação quando configurada.
   Depois, gates, pytest e aceitação são repetidos. Os erros são enviados ao
   builder como diagnósticos; não incluas segredos nessas mensagens.
5. Uma exceção no validador ou uma resposta mal formada é erro de infraestrutura:
   propaga-se e não desencadeia reparação. A telemetria regista a falha sem guardar
   a mensagem da exceção. Contratos alterados também impedem reparação.
6. Lê `tests/test_acceptance.py`. O teste de integração exige um README apesar
   de os testes gerados passarem, e verifica nova aceitação após correção.

```python
from app.builder.harness import BuilderHarness

def acceptance(workspace):
    if not (workspace / "README.md").is_file():
        return ["README.md is required"]
    return []

harness = BuilderHarness(acceptance_validator=acceptance, max_repair_attempts=2)
# harness.build("O pedido")  # chama modelos reais por omissão
```

```powershell
.venv\Scripts\python.exe -m pytest tests/test_acceptance.py -q
```

Este exemplo valida um requisito de entrega, não o comportamento do agente.
Para aceitação funcional, escreve verificações específicas dos inputs/outputs
esperados, independentes dos testes que o builder pode alterar.

## Limites

A independência é de autoria e localização, não isolamento de segurança.
O validador corre no processo do harness; não importes código gerado não fiável
diretamente. A execução controlada em processo isolado fica para outra etapa.
Não há timeout automático para esta função. Deve ser curta e determinística;
chamadas externas ou pagas não são contabilizadas automaticamente por este hook.

Não existe uma suite universal de aceitação: sem função configurada, esta etapa
não corre. O código do verificador ainda não é versionado no relatório. Esta
integração permite critérios independentes, mas não prova qualidade científica
nem impede que testes gerados sejam enfraquecidos entre reparações.
