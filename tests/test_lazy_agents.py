import subprocess
import sys


def test_importing_agents_does_not_construct_a_model():
    # Processo novo para não depender dos módulos já importados pelo pytest.
    script = """
import app.models
def forbidden():
    raise AssertionError('get_model called during import')
app.models.get_model = forbidden
import app.builder.harness
import app.planning.capability_planner
"""
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
