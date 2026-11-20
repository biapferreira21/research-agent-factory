from app.planning.capability_planner import plan_capabilities
from app.schemas.agent import AgentSpec, ModelSpec


spec = AgentSpec(
    name="file_test_agent",
    description="Agent that reads files and helps run tests.",
    objective=(
        "Read files from an authorized workspace and "
        "run Python tests safely."
    ),
    inputs=[
        "file path",
        "test request",
    ],
    outputs=[
        "file content",
        "test result",
    ],
    architecture="single_agent",
    model=ModelSpec(
        provider="openai",
        model="gpt-5.5",
        temperature=0.0,
    ),
    system_prompt=(
        "Read files and run tests safely inside "
        "the authorized workspace."
    ),
)


capabilities = plan_capabilities(spec)


print()
print("=== CAPABILITY SPEC ===")
print()
print(
    capabilities.model_dump_json(
        indent=2,
    )
)

