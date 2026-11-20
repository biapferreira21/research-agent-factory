import pytest

from app.tools.filesystem import create_filesystem_tools


def tools_for(path):
    return {tool.name: tool for tool in create_filesystem_tools(path)}


def test_build_tools_keep_independent_roots(tmp_path):
    first = tools_for(tmp_path / "first")
    second = tools_for(tmp_path / "second")
    first["write_file"].invoke({"path": "agent.py", "content": "first"})
    second["write_file"].invoke({"path": "agent.py", "content": "second"})
    assert first["read_file"].invoke({"path": "agent.py"}) == "first"
    assert second["read_file"].invoke({"path": "agent.py"}) == "second"
    assert first["list_files"].invoke({}) == "agent.py"
    assert "run_pytest" not in first


@pytest.mark.parametrize("path", ["../other/file.py", "../../file.py", "C:/outside.py", "/outside.py", "C:outside.py", "agent_spec.json:stream", "agent_spec.json.", "agent_spec.json "])
@pytest.mark.parametrize("name", ["write_file", "read_file", "list_files"])
def test_scoped_tools_reject_unsafe_paths(tmp_path, path, name):
    tools = tools_for(tmp_path / "build")
    args = {"path": path}
    if name == "write_file":
        args["content"] = "blocked"
    with pytest.raises(ValueError):
        tools[name].invoke(args)


@pytest.mark.parametrize("path", ["agent_spec.json", "./agent_spec.json", "nested/../agent_spec.json"])
def test_spec_is_readable_but_not_writable(tmp_path, path):
    (tmp_path / "agent_spec.json").write_text("approved", encoding="utf-8")
    tools = tools_for(tmp_path)
    with pytest.raises(ValueError, match="read-only"):
        tools["write_file"].invoke({"path": path, "content": "changed"})
    assert tools["read_file"].invoke({"path": "agent_spec.json"}) == "approved"
