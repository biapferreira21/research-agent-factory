# Etapa 6A — decisões tipadas e routing testável

Criámos um serviço local para escolher entre candidatos previamente aprovados.
O primeiro uso é model routing. Não instalámos nem chamámos JEV, nem adicionámos
modelos ou serviços pagos. A integração real com JEV continua pendente.

## 1. Separar três responsabilidades

```text
Model Registry + política + orçamento
        → candidatos elegíveis
        → decisor escolhe um ID
        → validação da resposta e confiança
        → revalidação de elegibilidade
        → criação do cliente
```

O catálogo determina o que pode ser usado. O decisor escolhe apenas entre essas
opções. O harness continua a controlar execução, orçamento e validação.

O routing acontece quando `get_model()` cria um cliente para um papel do build.
Não troca de modelo em cada iteração interna de um agente LangChain já criado.
Também não está ligado ao runtime dos agentes gerados.

## 2. Definir os contratos

Começa por `app/decisions/schemas.py`:

- `ModelChoice`: ID, provider, modelo, reserva e capacidades de um candidato.
- `DecisionState`: etapa, modelo preferido, saldo e hash do protocolo, quando existe.
- `DecisionRequest`: ID único do pedido e candidatos.
- `DecisionResponse`: ID do pedido, escolha, confiança e probabilidades opcionais.
- `DecisionPolicy`: limiar de confiança e ação de baixa confiança.
- `DecisionRecord`: registo auditável de uma tentativa.
- `DecisionResult`: escolha aceite, origem e indicação de fallback.

O contrato atual é específico de `model_routing`. A seleção de MCPs, RAG e dimensões
de avaliação ainda não usa este serviço. O estado também não inclui o texto completo
da tarefa/protocolo; terá de evoluir conforme os requisitos do adaptador real.

Usamos Pydantic para rejeitar valores inválidos: confiança fora de [0,1], NaN,
infinitos e IDs de candidatos repetidos. Os contratos são imutáveis para evitar
alterações acidentais durante a decisão.

## 3. Definir a interface do decisor

Em `app/decisions/service.py`, `DecisionBackend` é um `Protocol` Python:

```python
class DecisionBackend(Protocol):
    name: str
    def decide(self, request: DecisionRequest) -> DecisionResponse: ...
```

Descreve os atributos/métodos esperados sem prender o serviço a uma API externa.
Um adaptador JEV futuro terá de traduzir o pedido e devolver este contrato; não
estamos a afirmar que este seja o formato nativo da API JEV.

Em `backends.py` há duas implementações locais:

- `ConfiguredModelBackend`: mantém o modelo configurado, se estiver nos candidatos.
- `FixedDecisionBackend`: decisor falso que devolve uma escolha/confiança definidas
  pelo teste ou exercício.

A regra configurada devolve 1.0 por ser uma escolha determinística. Não é uma
probabilidade calibrada nem uma avaliação da qualidade científica do modelo.

## 4. Validar a resposta

O serviço revalida a resposta mesmo que o backend devolva um objeto Python que
tenha sido construído sem validação. Exige:

1. O ID do pedido correto.
2. Uma escolha que pertença aos candidatos recebidos.
3. Confiança numérica, finita e dentro de [0,1].
4. Se houver probabilidades, uma por candidato, sem repetições, com soma 1 dentro
   de uma tolerância de 0,000001.

Esta validação não prova calibração ou coerência científica. A confiança e a
probabilidade de cada escolha são campos distintos; não exigimos que sejam iguais.

Sem candidatos, o backend nem sequer é chamado. Uma resposta inválida ou uma
exceção do backend bloqueia: não usamos fallback para disfarçar esses erros.

## 5. Baixa confiança e fallback

O default é confiança mínima 0,80 e bloqueio abaixo desse valor. É uma política
inicial configurável, não um limiar empiricamente validado para JEV.

Um fallback precisa de duas escolhas explícitas no código:

```python
service = DecisionService(
    primary=FixedDecisionBackend("openrouter:openrouter/free", confidence=0.40),
    policy=DecisionPolicy(on_low_confidence="fallback"),
    fallback=ConfiguredModelBackend(),
)
```

Há no máximo uma tentativa primária e uma de fallback. O fallback recebe os mesmos
candidatos e tem de passar pela mesma validação e limiar. Também pode ser recusado.
Não há loop, escalada para um modelo pago nem pergunta automática ao utilizador.

Para testar o routing num build, podes injetar esse serviço no construtor:
`BuilderHarness(decision_service=service)`. Isto configura o harness; chamar um
build com planners reais pode fazer chamadas a modelos como nas etapas anteriores.

## 6. Integrar com catálogo e orçamento

Lê `app/decisions/model_router.py` e depois `app/models.py`:

- Filtra aprovação, validade dos preços, capacidades, routers e orçamento disponível.
- Mantém os candidatos dentro do provider atualmente configurado; não muda contas/providers.
- Inclui a reserva manual quando esta é superior à reserva do catálogo.
- Bloqueia se existir custo desconhecido num orçamento limitado ou se este já foi excedido.
- Depois da decisão, volta a verificar preço/elegibilidade e saldo.
- Cria o cliente com o modelo escolhido e o seu limite de output.

A reserva efetiva ainda acontece no callback imediatamente antes da chamada.
Assim, aceitar uma decisão não gasta dinheiro nem garante que a chamada seguinte
será autorizada: outro consumo pode esgotar o saldo entretanto.

Sem serviço injetado, preservamos o modelo configurado. Se esse modelo deixar de
ser elegível, bloqueamos em vez de escolher outro silenciosamente. Fora de um
build ativo, mantém-se a validação direta do catálogo, sem serviço de decisões.

## 7. Guardar as tentativas

`BuildTelemetry.record_decision` acrescenta linhas a
`.factory_runs/<build_id>/decisions.jsonl`. Regista candidatos, estado, política,
backend, tentativa, resposta válida e resultado da validação. Não guarda prompts,
credenciais, respostas malformadas ou mensagens completas de exceções.

`accepted` significa que o serviço aceitou a decisão; não significa que o cliente
foi criado, a chamada foi executada ou a investigação teve sucesso. O estado final
do build e os registos de utilização respondem a essas outras perguntas.

Os backends atuais são regras locais sem custo de API. Quando ligarmos JEV ou um
fallback por LLM, será necessário acrescentar limites de tempo, contabilização
das chamadas ao decisor e tratamento do contrato real. Essa parte ainda não existe.

## 8. Executar e estudar

```powershell
.\.venv\Scripts\python.exe decision_demo.py
.\.venv\Scripts\python.exe research_harness_demo.py
.\.venv\Scripts\python.exe -m pytest tests -q
```

O primeiro comando demonstra bloqueio e fallback, sem chamar modelos. O segundo
confirma que o exemplo científico anterior continua funcional. Como os planners
do exemplo científico são falsos e não chamam `get_model()`, não criam decisões
de routing; os testes de integração cobrem esse caminho com clientes falsos.

Ordem de estudo: schemas → backends → service → demo → model_router → app/models.py.
Depois lê `tests/test_decisions.py` e `tests/test_model_routing.py`.

Exercício: no decisor falso, troca o ID por um modelo não aprovado. Mesmo com
confiança 1.0, a escolha tem de ser recusada. Depois muda apenas a confiança para
0.80 e observa a aceitação no limite exato da política.
