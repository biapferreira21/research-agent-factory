
from app.builder.harness import BuilderHarness

harness = BuilderHarness()

result = harness.build(
    "I want to create an agent that can read files and run tests."
)



print()
print("=== BUILD ===")
print()
print(f"Build ID: {result.build_id}")
print(f"Agent: {result.agent_name}")
print(f"Workspace: {result.workspace}")
print(f"Status: {result.status}")


print(f"Repair attempts: {result.repair_attempts}")

if result.errors:
    print()
    print("=== ERROS DO BUILD ===")

    for error in result.errors:
        print(error)
