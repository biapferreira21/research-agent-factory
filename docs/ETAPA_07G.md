# Etapa 7G — guardar e reler avaliações

`app/planning/result_store.py` acrescenta um arquivo local, independente do harness.
Não executa experiências nem implica aprovação dos resultados guardados.

## Ordem de estudo

1. Lê `save_evaluation`. Revalida os contratos e calcula o relatório antes de
   criar uma pasta UUID nova. Nunca reutiliza uma pasta anterior.
2. Observa os ficheiros `protocol.json`, `results.json` e `evaluation.json`.
   Os valores estruturados são conservados. Resultados estruturalmente inválidos
   também podem ser guardados para diagnóstico, com estado `invalid_results`.
3. O manifesto inclui versão do formato, versão do avaliador e hash de cada
   ficheiro. É escrito por último. Sem manifesto válido, o arquivo não está
   concluído. Uma interrupção pode deixar uma pasta parcial, que não é apagada
   automaticamente nem aceite pelo leitor. Não há garantia transacional/fsync.
4. Segue `load_evaluation`. Só lê nomes fixos, recusa links simbólicos nos
   artefactos, valida hashes e versões, reconstrói os contratos e recalcula o
   relatório. Um relatório diferente do recalculado é rejeitado.
5. Executa `result_store_demo.py`: cria dados sintéticos, guarda-os e relê-os.
   A pasta fica em `generated_agents/.research_evaluations/<uuid>`.
6. Lê `tests/test_result_store.py`: inclui alteração de cada ficheiro, ausência
   de manifesto e um relatório alterado com checksum também atualizado.

```powershell
.venv\Scripts\python.exe result_store_demo.py
.venv\Scripts\python.exe -m pytest tests/test_result_store.py -q
```

## Limites

O limite é de 10 MB por artefacto. Hashes detetam mudanças relativamente ao
manifesto; não são assinaturas nem provam autenticidade. Quem puder alterar
todos os ficheiros e hashes pode produzir outro arquivo coerente. O recálculo
verifica consistência aritmética, não se as medições foram realmente executadas.

`relative_mean_v1` identifica a semântica atual do avaliador; futuras alterações
de semântica precisam de nova versão e uma política explícita de migração.
Não há migração automática de hashes de protocolos antigos.

As versões declaradas de código e dataset não incluem cópias desses recursos.
Portanto, o arquivo permite repetir a avaliação dos números guardados, mas não
reproduzir uma experiência completa. Não há ligação a um build, runner experimental,
isolamento de execução ou orçamento de investigação nesta etapa.
