RESEARCH AGENT FACTORY // KIT 0.1.1

WINDOWS

1. Install Python 3.12 or 3.13 from python.org.
2. Double-click "Install Agent Factory.cmd" once.
3. Double-click "Start Agent Factory.cmd" whenever you want to use it.
4. In the browser, open I/O (⌬) and connect your own API key.

Your keys, projects, documents and memory stay inside this extracted folder's
private data directory. They are never included in the original download.

OBSIDIAN

Open I/O (⌬), enter the absolute path of an existing vault, and select LINK.
Inside a project, open Memory and select SYNC.

PYTHON SDK

After installation:

    .venv\Scripts\python.exe -c "from app import AgentFactoryClient; print(AgentFactoryClient)"

See SDK.md for a complete example.

MACOS / LINUX

    python3 -m venv .venv
    .venv/bin/python -m pip install packages/research_agent_factory-0.1.1-py3-none-any.whl
    .venv/bin/python -m app serve --host 127.0.0.1 --port 8765 --data data

Then open http://127.0.0.1:8765/.
