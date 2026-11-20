# Etapa 8F — listar builds e escolher um relatório

O comando da etapa 8E permite agora listar os builds existentes, sem executar
agentes, testes ou chamadas a modelos.

```powershell
.venv\Scripts\python.exe build_report.py --list
.venv\Scripts\python.exe build_report.py --list --limit 2 --offset 0
.venv\Scripts\python.exe build_report.py --list --limit 2 --offset 2
.venv\Scripts\python.exe build_report.py UUID_DO_BUILD
```

Substitui o UUID pelo `build_id` de uma entrada. Usa `--root` se o harness tiver
guardado os builds numa raiz diferente da configurada.

## Ordem de estudo

1. Em `app/telemetry/report.py`, lê `list_builds`. Só considera subpastas com
   UUID canónico em `.factory_runs`. Ignora outros nomes e links simbólicos.
2. Ordena pela data de modificação da pasta, mais recente primeiro; UUID resolve
   empates. Isto não é a data de criação nem necessariamente a última atividade
   num ficheiro já existente. Cópias ou edições podem mudar a ordenação.
3. `limit` controla o tamanho da página, entre 1 e 100. `offset` indica quantos
   builds saltar. `next_offset=null` significa que não há outra página.
4. A listagem reutiliza `build_report`, mas não percorre os arquivos científicos.
   Mostra apenas UUID, estado, última etapa, etapas de reparação iniciadas e avisos.
   Para custos, aceitação e avaliações associadas, consulta o UUID individualmente.
5. Logs ilegíveis produzem `unreadable` para aquela entrada, preservando o resto
   da lista. `incomplete` não distingue execução em curso de interrupção.
6. Em `build_report.py`, observa argparse: escolhe um UUID ou `--list`. Os
   argumentos de paginação pertencem à listagem.
7. Lê `tests/test_build_listing.py`: valida ordenação, paginação, limites,
   raiz vazia e erro num build sem ocultar os restantes.

```powershell
.venv\Scripts\python.exe -m pytest tests/test_build_listing.py tests/test_build_report.py -q
```

Uma raiz existente sem `.factory_runs` devolve lista vazia. Uma raiz inexistente
é erro de leitura. A paginação é sobre o filesystem atual, sem fotografia
transacional: alterações durante a consulta podem deslocar entradas entre páginas.
O scan enumera as pastas e lê logs apenas da página pedida, sem cache persistente.

Esta etapa é só de leitura. Não retoma, apaga, arquiva ou modifica builds.
