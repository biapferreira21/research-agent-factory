"""Pipeline científico offline. Prepara um plano; não executa experiências."""

from pathlib import Path

from app.builder.harness import BuilderHarness
from app.schemas.agent import AgentSpec, EvaluationSpec, ModelSpec
from app.schemas.research import ResearchProtocol, ResearchQuestionSpec
from app.tools.filesystem import create_filesystem_tools
from harness_offline_demo import offline_capability_planner
from research_demo import create_example_protocol


DEMO_QUESTION = "A estratégia A reduz o erro relativamente à estratégia B?"


def offline_question_formalizer(request: str) -> ResearchQuestionSpec:
    # Stub para o exemplo A/B; não interpreta perguntas arbitrárias.
    if request != DEMO_QUESTION:
        raise ValueError("Este demo só conhece a pergunta A/B indicada em DEMO_QUESTION.")
    return create_example_protocol().question


def offline_research_planner(question: ResearchQuestionSpec) -> ResearchProtocol:
    data = create_example_protocol().model_dump()
    data["question"] = question.model_dump()
    data["assumptions"] = ["Parâmetros didáticos fixos; não foram escolhidos por análise científica."]
    return ResearchProtocol.model_validate(data)


def offline_scientific_architect(protocol: ResearchProtocol) -> AgentSpec:
    return AgentSpec(
        name="research_plan_demo", description="Preparar o plano de uma experiência comparativa",
        objective=protocol.question.question, inputs=protocol.question.inputs,
        outputs=["Plano de execuções, sem resultados experimentais"], architecture="workflow",
        model=ModelSpec(provider="openrouter", model="unused-offline"),
        system_prompt="Ler o protocolo protegido e apresentar o plano, sem afirmar que foi executado.",
        assumptions=protocol.assumptions,
        evaluations=[EvaluationSpec(
            name="protocol_compliance", description="Preservar seeds, baselines e métricas no plano",
            success_criteria="O plano contém os valores exatos do protocolo e o estado planned_not_executed.",
        )],
    )


class OfflineResearchBuilder:
    def __init__(self, workspace: Path):
        self.tools = {tool.name: tool for tool in create_filesystem_tools(workspace)}

    def invoke(self, payload: dict, *, config: dict) -> None:
        protocol = ResearchProtocol.model_validate_json(self.tools["read_file"].invoke({"path": "research_protocol.json"}))
        source = '''import json
from pathlib import Path


def experiment_plan():
    protocol = json.loads(Path(__file__).with_name("research_protocol.json").read_text(encoding="utf-8"))
    return {
        "question": protocol["question"]["question"],
        "metrics": [metric["name"] for metric in protocol["metrics"]],
        "baseline_runs": [{"baseline": baseline, "seed": seed}
                          for baseline in protocol["baselines"] for seed in protocol["seeds"]],
        "status": "planned_not_executed",
    }


if __name__ == "__main__":
    print(json.dumps(experiment_plan(), ensure_ascii=False, indent=2))
'''
        expected_runs = [{"baseline": baseline, "seed": seed} for baseline in protocol.baselines for seed in protocol.seeds]
        tests = f'''from agent import experiment_plan


def test_plan_preserves_the_research_contract():
    plan = experiment_plan()
    assert plan["question"] == {protocol.question.question!r}
    assert plan["baseline_runs"] == {expected_runs!r}
    assert plan["metrics"] == {[metric.name for metric in protocol.metrics]!r}
    assert plan["status"] == "planned_not_executed"
'''
        self.tools["write_file"].invoke({"path": "agent.py", "content": source})
        self.tools["write_file"].invoke({"path": "tests/test_research_plan.py", "content": tests})


if __name__ == "__main__":
    harness = BuilderHarness(
        question_formalizer=offline_question_formalizer,
        research_planner=offline_research_planner,
        scientific_architect=offline_scientific_architect,
        capability_planner=offline_capability_planner,
        builder_factory=OfflineResearchBuilder,
    )
    result = harness.build_research(DEMO_QUESTION)
    print(f"Status: {result.status}")
    print(f"Workspace: {result.workspace}")
    print(f"Telemetria: {result.telemetry_path}")
    for error in result.errors:
        print(error)
