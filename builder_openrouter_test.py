from app.builder.agent import create_builder_agent
from app.config import get_workspace_root


request = """
This is a tool-calling smoke test.

Authorized workspace:
openrouter_smoke_test

Instructions:
- Use the write_file tool.
- Create exactly this file:
  ok.txt
- The file content must be exactly:
  OpenRouter Builder tools OK
- Then use read_file to read the same file.
- Do not create any other files.
- Finish with a short confirmation.
"""

builder_agent = create_builder_agent(get_workspace_root() / "openrouter_smoke_test")
result = builder_agent.invoke(
    {
        "messages": [
            {
                "role": "user",
                "content": request,
            }
        ]
    },
    config={
        "recursion_limit": 8,
        "max_concurrency": 1,
    },
)

print()
print("=== BUILDER OPENROUTER TEST ===")
print()
print(result["messages"][-1].content)

