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
    ),
    system_prompt="Responde de forma amigavel e educada",
)


repair_request = f"""
Workspace:
hello_agent

The generated project failed Factory contract checks.

Failures:
1. agent.py does not actually use LangChain.
2. The production agent does not actually use the model/provider declared
   in the AgentSpec.

The current deterministic Python implementation is not sufficient.

Approved AgentSpec:

{spec.model_dump_json(indent=2)}

Repair instructions:
- Inspect the existing hello_agent files.
- Make the minimum necessary changes.
- The production agent must actually be implemented using LangChain.
- For architecture=single_agent, use LangChain create_agent.
- The production implementation must use the OpenAI model declared in the AgentSpec.
- Unit tests must NOT make real external API calls.
- Use mocks, fakes, or dependency injection in tests when necessary.
- Do not replace the LLM agent with if/else deterministic responses.
- Do not execute tests; validation belongs to the harness.
- Use paths relative to this build, such as agent.py.
- Work only inside the hello_agent workspace.
"""


builder_agent = create_builder_agent(get_workspace_root() / "hello_agent")
result = builder_agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": repair_request,
            }
        ]
    }
)


print()
print("=== REPAIR RESULT ===")
print()
print(result["messages"][-1].content)


