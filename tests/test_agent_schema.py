from app.schemas.agent import MemorySpec, RuntimeSpec, ToolSpec
def test_tool_spec_default():
    tool = ToolSpec(
        name="test_tool",
        description="Tool usada para teste",
    )

    assert tool.required is True


def test_memory_spec_defaults():
    memory = MemorySpec()

    assert memory.short_term is True
    assert memory.long_term is False


def test_runtime_spec_default():
    runtime = RuntimeSpec()

    assert runtime.persistence == "memory"


    