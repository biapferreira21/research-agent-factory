import pytest
import app.tools.filesystem as fs

def test_write_and_read_file(tmp_path, monkeypatch):
    monkeypatch.setattr(fs, "WORKSPACE_ROOT", tmp_path.resolve())
    fs.write_file.invoke(
        {
            "path": "agente_teste/hello.txt",
            "content": "Ola Agent Factory",
        }
    )
    content = fs.read_file.invoke(
        {
            "path": "agente_teste/hello.txt",
        }
    )
    assert content == "Ola Agent Factory"


def test_list_files(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    fs.write_file.invoke(
        {
            "path": "agente_teste/hello.txt",
            "content": "teste",
        }
    )

    files = fs.list_files.invoke(
        {
            "path": ".",
        }
    )

    assert "hello.txt" in files

def test_path_outside_workspace_is_blocked(tmp_path, monkeypatch):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    with pytest.raises(ValueError):
        fs.safe_path("../fora.txt")


def test_safe_path_allows_nested_path_inside_workspace(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    target = fs.safe_path(
        "agent/build/src/agent/__init__.py"
    )

    expected = (
        tmp_path
        / "agent"
        / "build"
        / "src"
        / "agent"
        / "__init__.py"
    ).resolve()

    assert target == expected


def test_safe_path_blocks_parent_traversal(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(
        fs,
        "WORKSPACE_ROOT",
        tmp_path.resolve(),
    )

    with pytest.raises(ValueError):
        fs.safe_path("../outside.txt")

