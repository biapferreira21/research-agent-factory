"""Biblioteca da factory: instruções verificadas por hash; nunca executa scripts importados."""
import hashlib
import json
from pathlib import Path

from app.config import PROJECT_ROOT
from app.decisions.schemas import DecisionRequest, DecisionState, OptionChoice
from app.retrieval.bm25 import rank
from app.telemetry.build import active_build


class SkillLibrary:
    def __init__(self, root: Path = PROJECT_ROOT):
        self.root = root.resolve()
        path = self.root / "config" / "skills_catalog.json"
        self.entries = json.loads(path.read_text(encoding="utf-8"))["entries"] if path.exists() else []

    def candidates(self, question, limit=12):
        enabled = [item for item in self.entries if item.get("enabled") and item.get("kind") == "skill"]
        docs = [item["id"] + " " + item.get("description", "") for item in enabled]
        ranking = rank(question, docs, limit=limit)
        lexical = [enabled[i] for i, _ in ranking]
        by_id = {item["id"]: item for item in enabled}
        text = question.lower()
        routed = ["dougtrajano-arxiv-search", "zsun79-write-literature-review"]
        routes = (
            (("machine learning", "neural", "model", "feature", "classification", "compression", "compressibility"),
             ("foryourhealth111-pixel-evaluating-machine-learning-models",
              "jaechang-hits-scikit-learn-machine-learning",
              "jeremylongshore-engineering-features-for-machine-learning")),
            (("regression", "econometric", "causal", "instrumental variable", "panel data", "ols"),
             ("brycewang-stanford-ols-regression", "brycewang-stanford-panel-data-analyst",
              "brycewang-stanford-iv-regression-guide")),
            (("statistic", "power", "hypothesis", "experiment", "exploratory data"),
             ("k-dense-ai-statistical-analysis", "k-dense-ai-statistical-power",
              "k-dense-ai-exploratory-data-analysis")),
            (("proof", "theorem", "topology", "symbolic", "mathemat"),
             ("findscripter-math-proof-writer", "matlab-matlab-symbolic-math",
              "brycewang-stanford-topology-data-analysis")),
            (("visual", "chart", "plot", "figure", "graph"),
             ("k-dense-ai-scientific-visualization", "brycewang-stanford-d3-visualization-guide",
              "brycewang-stanford-echarts-visualization-guide")),
        )
        for keywords, identifiers in routes:
            if any(keyword in text for keyword in keywords):
                routed.extend(identifiers)
        ordered = [by_id[identifier] for identifier in routed if identifier in by_id]
        ordered.extend(lexical)
        seen = set()
        return [item for item in ordered if not (item["id"] in seen or seen.add(item["id"]))][:limit]

    def read(self, identifier):
        entry = next((item for item in self.entries if item["id"] == identifier and item.get("enabled")), None)
        if entry is None:
            raise ValueError("Skill não disponível na biblioteca")
        path = (self.root / entry["path"]).resolve(strict=True)
        if not path.is_relative_to(self.root / "skills"):
            raise ValueError("Skill fora da biblioteca")
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != entry["sha256"]:
            raise ValueError("Skill alterada desde a importação")
        return raw.decode("utf-8")

    def select(self, question, *, service=None, max_skills=5):
        candidates = self.candidates(question)
        if service is None:
            return {"backend": "bm25", "selected": [item["id"] for item in candidates[:max_skills]],
                    "candidates": [item["id"] for item in candidates]}
        telemetry = active_build.get()
        if telemetry is None:
            raise ValueError("JEV requer telemetria e orçamento ativos")
        selected = []
        while candidates and len(selected) < max_skills:
            request = DecisionRequest(purpose="skill_selection", state=DecisionState(
                stage=telemetry.current_stage.value, preferred_choice_id=candidates[0]["id"], task=question[:5000],
                remaining_budget_usd=telemetry.tracker.summary().remaining_usd), candidates=tuple(
                    [OptionChoice(id=item["id"], description=item.get("description", item["id"])[:1500]) for item in candidates] +
                    [OptionChoice(id="none", description="No remaining skill is relevant to this research question")]))
            choice = service.decide(request, sink=telemetry.record_decision).choice_id
            if choice == "none":
                break
            selected.append(choice)
            candidates = [item for item in candidates if item["id"] != choice]
        return {"backend": service.primary.name, "selected": selected}

    def context(self, identifiers, max_chars=18000):
        selected = []
        identifiers = identifiers[:8]
        allowance = max_chars // max(1, len(identifiers))
        for identifier in identifiers:
            text = self.read(identifier)
            selected.append({"id": identifier, "instructions": text[:allowance],
                             "truncated": len(text) > allowance})
        return json.dumps(selected, ensure_ascii=False)
