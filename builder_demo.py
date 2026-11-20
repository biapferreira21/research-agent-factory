from app.builder.agent import create_builder_agent
from app.config import get_workspace_root
from app.schemas.agent import AgentSpec, ModelSpec


spec = AgentSpec(
    name="hello_agent",
    description="An agent that says hello",
    objective="Responder de forma amigavel",
    inputs=["mensagem do user"],
    outputs=["resposta do agente"],
    architecture="single_agent",
    model=ModelSpec(
        provider="openai",
        model="gpt-5.5",
        temperature=0.0
    ),
    system_prompt="Responde de forma amigavel e educada",
)

workspace="hello_agent"
request = f"""
Workspace autorizado para este build:
{workspace}
Implementa o AgentSpec abaixo:

{spec.model_dump_json(indent=2)}

Este é um teste inicial do Builder.

Requisitos:
- Trabalha apenas dentro de {workspace}
- Cria um projeto Python minimo.
- Cria pelo menos agent.py.
- Cria README.md.
- Cria testes dentro de tests/.
- Os testes nao devem fazer chamadas reais a APIs externas.
- Nao executes testes; a validacao pertence ao harness.
- Usa caminhos relativos a pasta deste build, como agent.py.
"""
builder_agent = create_builder_agent(get_workspace_root() / "hello_agent")
result = builder_agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": request,
            }
        ]
    }
)


print()
print("AgentSpec:")
print()
print(result["messages"][-1].content)




