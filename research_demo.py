r"""Executar com: .\.venv\Scripts\python.exe research_demo.py"""

from app.schemas.research import ResearchMetric, ResearchProtocol, ResearchQuestionSpec


def create_example_protocol() -> ResearchProtocol:
    question = ResearchQuestionSpec(
        question="A estratégia A reduz o erro relativamente à estratégia B?",
        domain="Otimização",
        hypothesis="A estratégia A produz menor erro médio no mesmo orçamento.",
        inputs=["Dataset sintético com versão e parâmetros registados"],
        constraints=["Mesmo dataset e orçamento de iterações nas duas estratégias"],
    )
    return ResearchProtocol(
        question=question,
        method="Comparar A e B em cada seed e guardar os resultados individuais.",
        baselines=["Estratégia B"],
        metrics=[ResearchMetric(
            name="mean_error",
            direction="minimize",
            measurement="Média do erro final nas três execuções de cada estratégia.",
        )],
        seeds=[11, 22, 33],
        success_criteria="Erro médio de A pelo menos 5% inferior ao de B.",
        stopping_rule="Parar após 100 iterações por estratégia e seed.",
        provenance_policy="Guardar versão do código, dataset, parâmetros e seed.",
        limitations=["Exemplo didático; três seeds não garantem significância estatística."],
    )


if __name__ == "__main__":
    protocol = create_example_protocol()
    print(protocol.model_dump_json(indent=2))
