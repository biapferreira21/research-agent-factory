# Interface source map

Every file required by the browser interface is stored in this repository. The
page does not load JavaScript, fonts, images, analytics, or styles from a CDN.

| Path | Purpose |
| --- | --- |
| `app/static/index.html` | Single-page application shell and accessible page structure. |
| `app/static/lab.css` | Complete responsive visual system, typography, chat and agent views. |
| `app/static/lab.js` | Navigation, project state, API calls, factory chat, agent chat and detail panels. |
| `app/static/scene.js` | Three.js mathematical background and pointer motion. |
| `app/static/vendor/three.core.js` | Local Three.js runtime. |
| `app/static/vendor/three.module.js` | Local Three.js ES module. |
| `app/static/vendor/THREE_LICENSE.txt` | Three.js MIT licence. |
| `app/static/assets/equations.png` | Mathematical blackboard texture supplied by the user. |
| `app/static/assets/research-figure.png` | Research visual supplied by the user. |
| `app/web.py` | FastAPI endpoints, session protection and static-file delivery. |
| `app/interface_harness.py` | Auditable map from the HTML build action to the complete Python factory pipeline. |
| `app/project_runtime.py` | Factory and research-agent chat execution. |
| `app/projects.py` | Persistent projects, sources, jobs and conversation storage. |

The original image provenance and publication note are recorded in
`docs/ASSETS.md`. Runtime data belongs in `data/`; it is deliberately excluded
from Git because it may contain private research material.
