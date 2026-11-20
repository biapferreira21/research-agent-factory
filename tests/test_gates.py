from app.builder.gates import (python_syntax_gate, required_structure_gate, run_all_gates)




def test_python_syntax_gate_accepts_valid_python(tmp_path):
    file_path = tmp_path / "valid.py"

    file_path.write_text(
        'print("ola")\n',
        encoding="utf-8",
    )

    errors = python_syntax_gate(tmp_path)

    assert errors == []


def test_python_syntax_gate_reports_invalid_python(tmp_path):
    file_path = tmp_path / "broken.py"

    file_path.write_text(
        "def hello(\n",
        encoding="utf-8",
    )

    errors = python_syntax_gate(tmp_path)

    assert len(errors) == 1
    assert "broken.py" in errors[0]


def test_required_structure_gate_accepts_valid_project(tmp_path):
    (tmp_path / "agent_spec.json").write_text(
        "{}",
        encoding="utf-8",
    )

    (tmp_path / "agent.py").write_text(
        'print("ola")\n',
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_agent.py").write_text(
        "def test_ok():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    errors = required_structure_gate(tmp_path)

    assert errors == []


def test_required_structure_gate_reports_missing_spec(tmp_path):
    (tmp_path / "agent.py").write_text(
        'print("ola")\n',
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_agent.py").write_text(
        "def test_ok():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    errors = required_structure_gate(tmp_path)

    assert "Missing required file: agent_spec.json" in errors


def test_required_structure_gate_reports_missing_tests(tmp_path):
    (tmp_path / "agent_spec.json").write_text(
        "{}",
        encoding="utf-8",
    )

    (tmp_path / "agent.py").write_text(
        'print("ola")\n',
        encoding="utf-8",
    )

    errors = required_structure_gate(tmp_path)

    assert "Missing required directory: tests" in errors


def test_run_all_gates_accepts_valid_project(tmp_path):
    (tmp_path / "agent_spec.json").write_text(
        "{}",
        encoding="utf-8",
    )

    (tmp_path / "agent.py").write_text(
        'print("ola")\n',
        encoding="utf-8",
    )

    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()

    (tests_dir / "test_agent.py").write_text(
        "def test_ok():\n"
        "    assert True\n",
        encoding="utf-8",
    )

    errors = run_all_gates(tmp_path)

    assert errors == []


    