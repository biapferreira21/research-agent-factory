# Atelier — Research Agent Factory

Aplicação local para organizar investigações, reunir documentos, selecionar skills e construir agentes Python com contratos, testes e registos de custos.

A interface está em inglês. Usa as duas imagens fornecidas para o ambiente visual e Three.js local para a geometria 3D. Consulta [a origem dos elementos visuais](docs/ASSETS.md).

## Abrir no Windows

Faz duplo clique em **Start Agent Factory.cmd**. O launcher confirma se o servidor já está ativo, inicia-o em segundo plano quando necessário e abre `http://127.0.0.1:8765/`.

Em alternativa, na pasta deste projeto:

```powershell
.\.venv\Scripts\python.exe -m app serve
```

Abre **http://127.0.0.1:8765**. Para instalar noutro ambiente, usa Python 3.12 ou 3.13, cria um virtualenv e executa `python -m pip install -e .`. A instalação editável mantém o catálogo e as skills nesta pasta. A suite foi executada em Python 3.14.7; LangChain ainda emite um aviso de compatibilidade Pydantic V1 nessa versão.

## Kit para partilha

O ficheiro `dist/research-agent-factory-kit-0.1.2.zip` pode ser enviado diretamente. Depois de extrair, um utilizador Windows executa **Install Agent Factory.cmd** uma vez e **Start Agent Factory.cmd** para abrir o harness. Cada pessoa liga as suas próprias chaves no painel **I/O**. Ao publicar uma tag Git `v*`, o workflow `publish-kit` cria automaticamente uma GitHub Release com o ZIP e o wheel para download.

## Percurso na interface

1. Cria uma investigação com nome, pergunta e domínio.
2. Em **Fontes & RAG**, adiciona PDF, DOCX, TXT, MD, CSV ou JSON. O original fica guardado e o texto é dividido em trechos com identificadores de citação. O limite é 20 MB por documento; PDF até 400 páginas. PDFs digitalizados precisam de OCR externo.
3. Pesquisa nos documentos usando BM25. É pesquisa lexical local, sem embeddings ou custo de modelo. Crossref/arXiv permitem descobrir literatura pública; os resultados não são automaticamente adicionados à RAG.
4. Em **Skills**, seleciona até oito instruções, pede uma proposta BM25 ou usa JEV. A seleção JEV exige API e tem orçamento próprio.
5. Em **Agents**, escolhe **Build research agent**. Esta ação envia a pergunta do projeto ao pipeline Python real (`BuilderHarness.build_research`): formaliza a pergunta, planeia e valida um protocolo, escolhe skills e ferramentas aprovadas, gera o agente e executa os testes produzidos. O limite por build começa em US$ 1 e pode ser alterado em **Build settings**. O modo demonstração continua disponível por CLI para desenvolvimento offline; não é a ação principal da interface.
6. Em **Agents**, fala primeiro com o **Agent Factory**, o coordenador do projeto, e usa **Build research agent** quando estiveres pronto para criar o agente. Abre cada build para consultar a ficha e usar o seu chat individual. O chat individual segue o `AgentSpec`, o modelo, as skills e a RAG do projeto; as conversas ficam separadas por agente. Para pedidos de literatura, pode pesquisar Crossref/arXiv através das ferramentas web aprovadas e devolve as fontes usadas. O chat não importa nem executa diretamente o `agent.py` gerado.
7. Importa medições `ExperimentResults` no painel **Avaliar medições**. O avaliador verifica protocolo, seeds, métricas e baselines; guarda um relatório com hashes. Nunca transforma medições sintéticas em resultados reais.
8. Em **Memory**, escreve decisões e próximos passos. As notas mais recentes entram como memória de referência nos chats seguintes e ficam associadas à ficha de cada agente. Adições de fontes, alterações de skills, builds e avaliações criam entradas automáticas. Em **I/O**, podes ligar uma pasta de vault Obsidian; **SYNC** exporta a memória do projeto e importa ficheiros Markdown criados ou alterados no respetivo diretório do vault.

## Configuração e custos

Liga OpenRouter ou OpenAI no painel **I/O**. As chaves ficam em `data/credentials.env`, nunca são devolvidas pela API e estão excluídas do Git e dos pacotes. O `.env`, usando `.env.example` como referência, continua disponível como alternativa para desenvolvimento. Nunca coloques chaves em documentos ou código gerado. O diagnóstico `python -m app doctor` apenas mostra se existe uma chave, não o valor.

- Modelo padrão: `openai/gpt-6-luna` através do OpenRouter. O backend rejeita `openrouter/free`, modelos `:free`, entradas com preço zero e routers variáveis, mesmo quando pedidos diretamente pela API. O catálogo aprovado e os preços verificados ficam em `config/model_registry.json`.
- Chats têm um limite de 60 segundos por chamada e builds 150 segundos por etapa, configuráveis com `MODEL_CHAT_TIMEOUT_SECONDS` e `MODEL_BUILD_TIMEOUT_SECONDS`. Respostas estruturadas inválidas não são repetidas indefinidamente: o pipeline usa o fallback validado. Um watchdog liberta o projeto quando uma operação deixa de mostrar progresso.
- A pesquisa académica consulta arXiv, Crossref, OpenAlex e Semantic Scholar em paralelo, com um limite de 20 segundos por fonte, para impedir que uma fonte lenta bloqueie todo o agente.
- Orçamento inicial da interface: **US$ 1 por build**, ajustável manualmente entre US$ 0,01 e US$ 1. O servidor rejeita valores acima desse teto. O valor escolhido fica no registo de custos daquele agente e abrange decisões JEV e reparações. Cada consulta com modelo e seleção JEV avulsa tem orçamento separado de US$ 1.
- Custos desconhecidos bloqueiam chamadas seguintes. As reservas reduzem o risco de exceder o orçamento, mas não constituem um limite de cobrança imposto pelo fornecedor. Uma chamada já enviada pode reportar um custo superior ao reservado.
- Nos modos reais, pergunta, contexto recuperado e instruções selecionadas podem ser enviados ao fornecedor configurado. BM25 e demonstração não enviam esses dados a modelos.
- JEV escolhe entre candidatos autorizados; não escreve o código do agente.

## Biblioteca de skills e MCPs

`config/skills_catalog.json` contém as 55 referências únicas pedidas. As cópias estão em `skills/imported/`, com `source.json`, hash e licença upstream quando encontrada. `scripts/import_research_library.py` permite voltar a importar. As instruções são usadas como contexto metodológico; **scripts importados não são automaticamente executados**, e recursos/dependências externos não são instalados só por aparecerem num SKILL.md. Alguns recursos referenciados não foram encontrados; consulta `missing_resources` e `files`.

As referências MCP externas são documentação, não ligações autenticadas. GitHub, Supabase, Firecrawl, Exa, Chrome, tldraw e restantes serviços exigem os seus adaptadores/configurações antes de serem usados pelo runtime. Não existe ainda um adaptador genérico para todos esses serviços.

Os dois MCPs próprios têm transporte stdio funcional:

```powershell
python -m app.mcp_server bm25 --root data --project-id UUID_DO_PROJETO
python -m app.mcp_server web
```

BM25 expõe pesquisa, documentos e leitura de trechos do projeto fixado. Web expõe pesquisa Crossref/arXiv e leitura em domínios científicos aprovados. Quando a API Atom do arXiv devolve 406 para uma consulta válida, o servidor usa a pesquisa HTML pública do próprio arXiv como alternativa, mantendo o limite de resultados. O cliente em `app/runtime_tools.py` fornece ao agente as ferramentas selecionadas no contrato. A restrição é da API das ferramentas; código Python arbitrário continua a poder aceder ao sistema.

## Comandos úteis

```powershell
python -m app doctor
python -m app demo --root generated_agents
python -m app skills --query "panel data regression"
python -m app build "A pergunta de investigação" --research --config examples/run.local.json
python -m app list --root generated_agents
python -m app show BUILD_UUID --root generated_agents
python -m app evaluate BUILD_UUID measurements.json --root generated_agents
python -m pytest -q
```

## Dados e limites atuais

`data/factory.sqlite3` guarda projetos, metadados, trechos, mensagens e operações. `data/projects/<uuid>/documents/` guarda originais; `wiki/` guarda entradas Markdown por projeto. Builds, logs e avaliações ficam na pasta de cada projeto. Para fazer backup, para o servidor e copia a pasta `data` inteira. Um reinício marca operações em curso como interrompidas; não existe retoma de checkpoints.

Por omissão, o servidor liga apenas a localhost e usa proteção de origem e token de sessão para escritas. É uma aplicação pessoal, sem autenticação multiutilizador. **Os testes de código gerado executam neste computador, sem isolamento do sistema operativo**. A passagem em pytest não comprova qualidade científica nem ausência de efeitos laterais.

Ainda não implementado: RAG vetorial/híbrida, execução isolada e padronizada de qualquer agente gerado, ligação universal aos MCPs externos, geração de avaliações por LLM independente e todas as decisões de arquitetura/RAG por JEV. Os chats usam os contratos, skills, RAG e ferramentas de pesquisa aprovadas; não importam nem executam o código Python gerado.

Consulta [o guia de estudo](docs/GUIA_DE_ESTUDO.md) para acompanhar o código por ordem, [o mapa da interface](docs/INTERFACE_FILES.md) para localizar cada ficheiro e [a rastreabilidade do harness](docs/HARNESS_TRACEABILITY.md) para seguir cada ação HTML até ao Python executado. Para GitHub, Docker e domínio, segue [o guia de publicação](DEPLOYMENT.md). As etapas antigas em `docs/ETAPA_*` e `ROTEIRO.md` conservam o histórico pedagógico.

Para controlar o harness a partir de outro programa Python, consulta [SDK.md](SDK.md). As regras de chaves e publicação estão em [SECURITY.md](SECURITY.md).
