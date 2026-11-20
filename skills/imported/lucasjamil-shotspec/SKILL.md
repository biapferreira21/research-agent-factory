---
name: shotspec
description: Convert a screenshot of a website, app, or social media post into clean, structured Markdown optimized for feeding to LLMs. Works in two modes. CONTENT mode turns a tweet, post, thread, chat, article, or dashboard into faithful machine-readable text for use as LLM context. DESIGN mode turns a screenshot of a good-looking site or app into a precise design spec covering colors, typography, spacing, layout, components, and imagery style, so an LLM can rebuild the UI in that style instead of guessing from a raw image. Use this skill whenever the user uploads an image of a web page, app UI, dashboard, or social post and wants it turned into Markdown, including phrasings like "make this into markdown", "extract this", "turn this screenshot into context", "clone or recreate this design", "match this style", or "build a site that looks like this". Trigger it for any task where a captured visual needs to become token-efficient, machine-readable Markdown, whether the user wants the content, the design, or both.
---

# Screenshot to Context

Turn a screenshot into structured Markdown an LLM can consume reliably. There are two distinct jobs this skill does, and the **first decision is which one the user wants**:

- **Content mode** — capture *what the screen says*. For feeding a post/thread/chat/article/dashboard to an LLM as context. Goal: faithful, token-efficient transcription with recovered structure.
- **Design mode** — capture *how the screen looks*. For a developer who found a good-looking site/app and wants an LLM to rebuild a UI in that style. Goal: a precise, implementable design spec — colors, typography, spacing, layout, components, imagery — so the LLM reconstructs the aesthetic instead of hallucinating it from a raw image.

Many requests want **both** (the content *and* the look). When in doubt, ask one quick question; if the user gave a clear signal ("clone this", "match this style", "use as context", "paste to ChatGPT"), just proceed in that mode.

## Why this matters

LLMs reason far better over clean structured text than over a raw image dump. For content, a screenshot carries hierarchy (headings, who-said-what, metadata) that naive OCR loses. For design, an LLM handed a raw screenshot guesses at hex values, font families, and spacing — and gets them subtly wrong. Writing the design down as explicit tokens (this exact color, this spacing scale, this font stack) turns "looks vaguely like the image" into "matches the image". This skill's job is to recover that structure — semantic or visual — and encode it explicitly in Markdown.

## Step 0: Pick the mode

- Signals for **design mode**: "clone", "recreate", "match the style", "build something that looks like", "design system", "I like this UI", developer context (memory/conversation about building a site/app), or the screenshot is clearly chosen for its aesthetics rather than its text.
- Signals for **content mode**: "use as context", "paste to an LLM", "extract the text", "summarize", "what does this thread say", a social post / chat / article where the words are the point.
- Both → produce content first, then a `## Design Spec` section after it.

---

## CONTENT MODE

Goal: maximum signal, minimum noise — capture everything semantically meaningful, drop visual chrome, preserve structure.

1. **Classify the content type** (drives the template): social post · thread/comments · chat/messaging · article/web page · app/dashboard UI · data view · generic. Read `references/templates.md` for the per-type template.
2. **Transcribe faithfully.** Verbatim — do not paraphrase, summarize, or "fix" the content (even visible typos or wrong translations stay as-is). Preserve wording, numbers, names, handles. Flag uncertain text with `[?]` / `[illegible]`; never guess a number or name.
3. **Recover structure** — map visual hierarchy to Markdown headings, lists, tables, blockquotes, threading.
4. **Strip noise** — nav bars, menus, cookie banners, status bars, non-content buttons (Follow/Share), ads/suggested rails, decorative chrome. When unsure if something is content or chrome, keep it and mark `[ui: ...]`.
5. **Add the metadata header** (below) so the LLM knows what it's looking at.
6. **Describe non-text content briefly** — `[image: ...]`, `[chart: line chart, revenue rising Jan–Jun, values...]`. The downstream LLM can't see it.

### Content metadata header

```markdown
---
source_type: <social_post | thread | chat | article | app_ui | data_view | generic>
platform: <X / Reddit / Instagram / unknown>
captured: <date visible, or "not visible">
notes: <partial capture, stitched images, capture-tool watermark, etc.>
---
```

Only include fields you can fill. Don't invent a platform or date. If a capture tool (e.g. a Mobbin watermark) overlays the image, note it here — it's not part of the app.

---

## DESIGN MODE

Goal: a developer-ready design spec precise enough that an LLM rebuilds the look without seeing the image. Read **`references/design-spec.md`** for the full extraction checklist and output template — it is the heart of this mode. The short version:

Extract and write down, explicitly:

1. **Overall character** — one or two sentences: the vibe (minimal / brutalist / playful / corporate / editorial), light or dark, density, era.
2. **Color palette** — every distinct color as a hex estimate with a role: background, surface/card, primary text, secondary/muted text, primary accent/brand, secondary accent, borders, success/warning/error. Estimate hex from what you see and label it an estimate. Note where each is used.
3. **Typography** — for each text role (display/H1, headings, body, captions, labels): identify the font *family or a close web-safe / Google Fonts substitute* and the *classification* (serif / sans-serif / mono / slab), plus relative weight and size. If you recognize the font, name it; otherwise give a confident substitute (e.g. "geometric sans, similar to Inter or Geist").
4. **Spacing & layout** — the layout system (single column / sidebar+content / card grid / etc.), the spacing rhythm (tight vs generous; estimate a base unit like 4px/8px), container width feel, alignment, and grid columns where visible.
5. **Components** — the recurring building blocks (buttons, cards, inputs, nav, badges, tabs) with their style: corner radius, border vs shadow, fill vs outline, padding, hover affordances if inferable. Give buttons special attention (shape, radius, fill, text).
6. **Imagery & iconography** — what kind of images are used (product photography on white, lifestyle photos, illustrations, gradients, none), their treatment (rounded corners, full-bleed, aspect ratios), and the icon style (line/outline, filled, weight).
7. **Distinctive details** — anything that makes the design recognizable: a signature accent color, an unusual radius, a specific shadow, letter-spacing on headings, etc. These are what separate a faithful clone from a generic one.

Always state estimates as estimates. The value of this spec is that it's *actionable* — a developer should be able to paste it under "build a landing page using this design system" and get something that looks like the screenshot.

---

## Handling multiple screenshots

If several images form one thing (a long thread, a multi-screen flow, multiple pages of the same site), stitch them in order and de-duplicate at the seams. For **design mode** across several screens of the same product, produce **one** consolidated design spec — the system is shared; note any per-screen variations under the relevant component.

## Output

Default: emit the Markdown inside a fenced code block so it's one-tap copyable on mobile. For long outputs (roughly >40 lines), additionally write a `.md` file to `/mnt/user-data/outputs/` and present it. Brief one-line note before the block; no commentary after it.

See `references/templates.md` (content templates), `references/design-spec.md` (design extraction), and `references/examples.md` (worked before/after examples).
