from app.builder.planner import create_agent_spec

requirement = input("Enter your requirement: ")

spec = create_agent_spec(requirement)

print()
print("AgentSpec:")
print()
print (spec.model_dump_json(indent=2))

