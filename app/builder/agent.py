from langchain.agents import create_agent
from app.models import get_model
from app.builder.prompt import BUILDER_PROMPT
from pathlib import Path

from app.tools.filesystem import create_filesystem_tools


def create_builder_agent(workspace: Path):
    """Cada builder recebe ferramentas limitadas ao seu build."""
    return create_agent(
        model=get_model(),
        tools=create_filesystem_tools(workspace),
        system_prompt=BUILDER_PROMPT,
    )

