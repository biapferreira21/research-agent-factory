# Etapa 6B — adaptador HTTP JEV

O JEV pode agora ser injetado no harness como backend do DecisionService.
O comportamento por omissão continua a ser a regra local do modelo configurado.
Esta etapa foi validada com HTTP simulado; não executámos chamadas reais.

## Ordem de estudo

1. Lê `app/decisions/jev.py`: `decide` converte os candidatos numa pergunta
   Choice. Envia apenas o estado de routing e os metadados dos candidatos.
   Não envia o texto do pedido de investigação; o hash identifica o protocolo,
   mas não transmite o seu conteúdo. A qualidade semântica do routing ainda
   precisa de avaliação e de um catálogo com alternativas úteis.
2. Segue `tracker.reserve`: reserva USD 0,003 no mesmo orçamento do build,
   antes de qualquer HTTP. O orçamento configurado mantém-se em USD 1,00.
3. Observa o cliente `httpx`: endpoint e modelo fixos, timeout de 30 segundos
   configurável, sem retries, redirects ou proxies herdados do ambiente.
4. Segue a conversão em `DecisionResponse`: exige Choice, confiança,
   probabilidades de todos os candidatos e soma válida. O serviço aplica o
   limiar de confiança e a política de fallback já existentes.
5. Lê o `finally`: mesmo uma resposta inválida pode ter custado dinheiro.
   O custo reportado é guardado quando válido; se faltar, fica desconhecido
   e impede novas chamadas. Não inferimos custo zero de erros HTTP ou timeouts.
6. Executa `jev_offline_demo.py` e lê `tests/test_jev.py`. O MockTransport
   substitui a rede, exercitando a serialização HTTP e a contabilização.

```powershell
.venv\Scripts\python.exe jev_offline_demo.py
.venv\Scripts\python.exe -m pytest tests/test_jev.py -q
```

## Ligação explícita ao harness

Este exemplo faz chamadas reais quando `build` é executado. Usa a chave já
configurada através de Settings, nunca a escrevas no código:

```python
from app.builder.harness import BuilderHarness
from app.config import get_settings
from app.decisions.jev import JevBackend
from app.decisions.service import DecisionService

service = DecisionService(JevBackend(get_settings().openrouter_api_key))
harness = BuilderHarness(decision_service=service)
# result = harness.build("O teu pedido")
```

Não alterámos `.env` nem ativámos este backend automaticamente. O catálogo
generativo continua a aprovar apenas `openrouter/free`; JEV é um decisor pago
separado, não um gerador de código. Com um único candidato, a regra local
continua a ser a opção útil por omissão.

## Custos e limites

A reserva é uma margem local, não um teto imposto pelo fornecedor. Uma cobrança
superior ao orçamento é registada e bloqueia o prosseguimento; não pode ser
anulada pelo código. Preços/reserva devem ser revistos até 26/10/2026, após o
que o adaptador bloqueia chamadas. Pedidos acima de 16000 bytes são rejeitados
localmente; este limite não pretende contar tokens. Nesta versão exigimos
`usage.cost`; não estimamos a cobrança quando o campo está ausente.

O timeout limita operações de rede, não garante um prazo total absoluto.
Uma chamada interrompida pode ter sido cobrada: não é repetida automaticamente.
Confiança alta não demonstra que a seleção é correta.

Fonte reconfirmada em 20/11/2026: [modelo, endpoint e preço JEV no OpenRouter](https://openrouter.ai/typesafe/jev-1.13).
O endpoint é `/api/alpha/decisions`, modelo `typesafe/jev-1.13`; a fonte publica
USD 0,042 por milhão de tokens de entrada e saída gratuita. A reserva de USD
0,003 inclui margem sobre 64000 tokens a essa tarifa.

Faltam validação com o serviço real e avaliações de qualidade do routing.
As decisões para MCPs, RAG e avaliações continuam fora desta etapa.
