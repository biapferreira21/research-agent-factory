# Etapa 7A — recuperação local com proveniência

Implementámos a parte de recuperação do RAG: encontrar trechos relevantes em
fontes locais explicitamente selecionadas. Ainda não há geração de respostas
com esses trechos nem ligação automática ao harness.

## Estudar passo a passo

1. Em `app/retrieval/local.py`, começa por `Source`. O contrato distingue fontes
   globais, de domínio e de projeto. O validator impede combinações incoerentes.
2. Lê `Evidence`: o trecho transporta origem, linhas e SHA-256 do ficheiro
   inteiro. O hash identifica a versão dos bytes, não comprova a sua veracidade.
3. Segue `LocalIndex.__init__`. Recebe uma pasta e uma lista explícita de fontes,
   valida os caminhos, lê até 1 MB por fonte e divide o texto por grupos de linhas.
   O conteúdo fica numa fotografia em memória: editar o ficheiro exige reconstruir
   o índice para recuperar a nova versão. Não há persistência nesta etapa.
4. Lê `terms` e `search`. A pontuação é a fração de palavras distintas da pergunta
   encontradas no trecho. Não representa confiança, probabilidade ou qualidade
   científica. A ordenação usa caminho e linha para resolver empates.
5. Observa os filtros antes da pontuação. Fontes globais estão disponíveis sempre;
   domínio e projeto só entram quando coincidem com os filtros explícitos.
   Um projeto com domínio definido exige ambos. Sem filtros, só entram globais.
6. Executa `retrieval_demo.py`. As três notas em `examples/knowledge` são sintéticas.
7. Lê `tests/test_local_retrieval.py`: verifica proveniência, filtros, ranking,
   caminhos proibidos, fontes repetidas e rejeição de JSON.

```powershell
.venv\Scripts\python.exe retrieval_demo.py
.venv\Scripts\python.exe -m pytest tests/test_local_retrieval.py -q
```

Exercício: pesquisa sem `project="a"` e observa a exclusão da nota do projeto.
Depois troca a pergunta para uma palavra inexistente: o resultado deve ser vazio.

## Limites e próxima integração

Só aceitamos `.txt` e `.md` em UTF-8. JSON, tabelas e resultados experimentais
precisam de leitores próprios que mantenham os campos estruturados. Não há
embeddings, sinónimos, normalização de acentos, BM25 ou pesquisa vetorial.
O tamanho do trecho é medido em linhas, não tokens.

Os scopes são filtros de aplicação, não autenticação ou isolamento entre utilizadores.
Quem constrói o índice escolhe e classifica as fontes; essa classificação deve ser
revista. A validação de caminhos também não substitui uma sandbox do sistema operativo.

Na próxima integração será necessário selecionar fontes por build, guardar a
fotografia das evidências e impor um limite de contexto antes de as enviar aos
planners. Texto recuperado deve ser tratado como dados citáveis, nunca como
instruções que substituem as regras do agente. Nesta etapa nada é enviado a modelos.

Não há dependências novas, chamadas pagas ou alteração do orçamento de USD 1,00.
