"""Importar as referências pedidas para a biblioteca da factory, sem executar scripts."""
import concurrent.futures
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
REFERENCES = '''DougTrajano/pydantic-ai-skills/examples/skills/arxiv-search
Zsun79/LitReviewSkill/skills/write-literature-review
ShiyangZheng/scholarly
agentscope-ai/OpenJudge/skills/bib-verify
K-Dense-AI/scientific-agent-skills/skills/peer-review
K-Dense-AI/scientific-agent-skills/skills/scientific-visualization
K-Dense-AI/scientific-agent-skills/skills/statistical-power
K-Dense-AI/scientific-agent-skills/skills/statistical-analysis
K-Dense-AI/scientific-agent-skills/skills/exploratory-data-analysis
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/analysis/dataviz/d3-visualization-guide
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/analysis/dataviz/echarts-visualization-guide
foryourhealth111-pixel/Vibe-Skills/bundled/skills/statistical-analysis
jeremylongshore/claude-code-plugins-plus-skills/skills/12-data-analytics/cohort-analysis-creator
Prat011/awesome-llm-skills/document-skills/xlsx
matlab/agent-skills-playground/skills/matlab-symbolic-math
ECNU-ICALK/AutoSkill/SkillBank/ConvSkill/english_gpt3.5_8_GLM4.7/math-practice-game
findscripter/everything-skills/09-verticals/math-proof-writer
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/analysis/econometrics/iv-regression-guide
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/analysis/econometrics/panel-data-analyst
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/domains/math/topology-data-analysis
brycewang-stanford/Auto-Empirical-Research-Skills/skills/67-econfin-workflow-toolkit/ols-regression
brycewang-stanford/Auto-Empirical-Research-Skills/skills/61-phdemotions-research-methods/skills/eda
brycewang-stanford/Auto-Empirical-Research-Skills/skills/43-wentorai-research-plugins/skills/tools/ocr-translate/pdf-math-translate-guide
X-RayLuan/awesome-ceo-stack/ceo-skill/Openclaw-Study-Coach/.claude/skills/math-tutor
ECNU-ICALK/AutoSkill/SkillBank/ConvSkill/english_gpt3.5_8_GLM4.7/simple-math-proof-explanation-with-custom-terminology
foryourhealth111-pixel/Vibe-Skills/bundled/skills/evaluating-machine-learning-models
matlab/matlab-agentic-toolkit/skills-catalog/ai-and-statistics/matlab-use-machine-learning-apps
jaechang-hits/SciAgent-Skills/skills/scientific-computing/scikit-learn-machine-learning
charlieviettq/awesome-agent-skill/.cursor/skills/voltagent/data-ai/machine-learning-engineer
jeremylongshore/claude-code-plugins-plus-skills/skills/.curated/engineering-features-for-machine-learning
deveshpunjabi/3d-website-skill/skills/3d-website-architect
ntaffzii/Skill-Agents/skills/obsidian/obsidian-canvas
bob798/ai-skill-kit/creative/svg-generator
MN755/Codex-Mission_Control/plugins/mission-control/skills/mission-control-creative-web-artifacts
lucasjamil/shotspec
github/github-mcp-server/io.github.github/github-mcp-server
anthropics/skills/skills/skill-creator
ComposioHQ/awesome-claude-skills/artifacts-builder
shanraisshan/claude-code-best-practice/.claude/skills/agent-browser
tldraw/tldraw/io.github.tldraw/tldraw
ChromeDevTools/chrome-devtools-mcp/io.github.ChromeDevTools/chrome-devtools-mcp
firecrawl/firecrawl-mcp-server/io.github.firecrawl/firecrawl-mcp-server
exa-labs/exa-mcp-server/ai.exa/exa
eugeniughelbur/obsidian-second-brain
blazickjp/arxiv-mcp-server/io.github.blazickjp/arxiv-mcp-server
supabase/mcp/com.supabase/mcp
NVIDIA/skills/plugins/nvidia-skills/skills/nvidia-skill-finder
llmsresearch/paperbanana/io.github.llmsresearch/paperbanana
OpenOSINT/OpenOSINT/io.github.OpenOSINT/openosint
jezweb/claude-skills/plugins/cloudflare/skills/cloudflare-api
SylphxAI/pdf-reader-mcp/io.github.SylphxAI/pdf-reader-mcp
kostja94/marketing-skills/skills/analytics/seo/google-search-console
NicholasSpisak/second-brain/skills/second-brain-ingest
ggozad/haiku.rag/io.github.ggozad/haiku-rag
sergebulaev/linkedin-skills/.codex-marketplace/linkedin-skills'''.splitlines()


def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "Research-Agent-Factory/0.1"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read(2_000_001)
    if len(raw) > 2_000_000:
        raise ValueError("File too large")
    return raw


def import_reference(reference):
    owner, repo, *parts = reference.split("/")
    subpath = "/".join(parts)
    is_mcp = subpath.startswith(("io.github.", "com.", "ai."))
    identifier = re.sub(r"[^a-z0-9-]+", "-", owner.lower() + "-" + (parts[-1] if parts else repo).lower()).strip("-")
    dest = ROOT / "skills" / "imported" / identifier
    dest.mkdir(parents=True, exist_ok=True)
    record = {"id": identifier, "reference": reference, "repository": f"https://github.com/{owner}/{repo}",
              "kind": "mcp" if is_mcp else "skill", "status": "unavailable", "enabled": False,
              "execution": "instructions_only", "files": [], "description": reference}
    candidates = ["README.md"] if is_mcp else [f"{subpath}/SKILL.md".lstrip("/"), f"{subpath}/skill.md".lstrip("/"),
                                             f"{subpath}/README.md".lstrip("/"), "SKILL.md", "README.md"]
    for path in dict.fromkeys(candidates):
        try:
            url = f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{path}"
            raw = fetch(url)
            filename = "SKILL.md" if path.lower().endswith("skill.md") else "README.md"
            (dest / filename).write_bytes(raw)
            record.update(status="imported" if filename == "SKILL.md" else "reference_only",
                          enabled=filename == "SKILL.md", path=str((dest / filename).relative_to(ROOT).as_posix()),
                          source_url=url, sha256=hashlib.sha256(raw).hexdigest())
            record["files"].append(filename)
            text = raw.decode("utf-8", errors="replace")
            match = re.search(r"(?m)^description:\s*(.+)$", text)
            record["description"] = (match.group(1).strip('"\'') if match else text[:400]).strip()[:700]
            # Conservar os recursos explicitamente referidos, sem instalar ou executar nada.
            folder = str(PurePosixPath(path).parent)
            resources = set(re.findall(r"(?:scripts|references|assets)/[\w./-]+\.(?:py|md|json|txt|js|yaml)", text))
            missing = []
            for resource in sorted(resources)[:40]:
                if ".." in PurePosixPath(resource).parts:
                    continue
                try:
                    content = fetch(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{folder}/{resource}")
                    target = dest / resource
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(content)
                    record["files"].append(resource)
                except Exception:
                    missing.append(resource)
            record["missing_resources"] = missing
            break
        except Exception:
            continue
    for license_name in ("LICENSE", "LICENSE.md", "LICENSE.txt"):
        try:
            raw = fetch(f"https://raw.githubusercontent.com/{owner}/{repo}/HEAD/{license_name}")
            (dest / "UPSTREAM_LICENSE").write_bytes(raw)
            record["license_file"] = str((dest / "UPSTREAM_LICENSE").relative_to(ROOT).as_posix())
            break
        except Exception:
            continue
    (dest / "source.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record


if __name__ == "__main__":
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        records = list(pool.map(import_reference, REFERENCES))
    path = ROOT / "config" / "skills_catalog.json"
    path.write_text(json.dumps({"schema_version": 1, "entries": records}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({status: sum(r["status"] == status for r in records)
                      for status in ("imported", "reference_only", "unavailable")}))
