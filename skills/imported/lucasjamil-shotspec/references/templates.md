# Output Templates by Content Type

Read this after classifying the screenshot. Use the matching template. Templates are guides, not rigid forms — adapt fields to what's actually present, and never invent data.

All outputs begin with the universal metadata header defined in SKILL.md.

---

## Social post (X / Instagram / LinkedIn / Facebook / Threads)

```markdown
---
source_type: social_post
platform: X
captured: not visible
---

## Post

**Author:** Jane Doe (@janedoe) · Verified
**Posted:** 3h ago

> [verbatim post text, line breaks preserved]
>
> [second paragraph if any]

**Media:** [image: dashboard screenshot showing a sales graph]

**Engagement:** 1.2K likes · 340 reposts · 89 replies · 45K views

**Quoted post:**
> **@otheruser:** [text of the quote-tweeted post]
```

Notes: keep hashtags and @mentions inline as written. Keep emoji. If it's a thread by the same author, use the thread template below.

---

## Thread / comments (Reddit, X replies, forums, comment sections)

Represent reply nesting with indented blockquotes or nested bullets. Preserve scores/votes.

```markdown
---
source_type: thread
platform: Reddit
---

## r/subreddit — "Thread title"

**OP:** u/username · 847 upvotes · 6h
> [post body, verbatim]

### Comments

- **u/commenter1** (231 pts): [comment text]
  - **u/commenter2** (88 pts): [reply text]
    - **u/commenter1** (12 pts): [reply to reply]
- **u/commenter3** (45 pts): [top-level comment]
```

---

## Chat / messaging (WhatsApp, iMessage, Slack, Discord, DMs)

Preserve speaker, order, and timestamps. Distinguish sender vs. recipient clearly.

```markdown
---
source_type: chat
platform: WhatsApp
---

## Conversation: Jane ↔ You

- **Jane** (10:42): [message]
- **You** (10:43): [message]
- **Jane** (10:45): [message]
  - [attachment: photo]
- **You** (10:46): [message] ✓✓ read
```

For group chats, keep every distinct sender name. Note reactions as `[reaction: 👍 by Tom]`.

---

## Article / web page (blog, news, docs, marketing)

Recover the document outline. This is where heading hierarchy matters most.

```markdown
---
source_type: article
platform: example.com
---

# Article Title

**Author:** Name · **Published:** date · **Reading time:** 6 min

[Lead paragraph, verbatim.]

## Section heading

[Body text. Preserve paragraph breaks, lists, and emphasis.]

- bullet
- bullet

> [pull quote or blockquote as shown]

[image: diagram of the system architecture]
```

Drop nav, sidebars, related-article rails, newsletter popups, and footers.

---

## App / dashboard UI (SaaS, mobile app, settings)

Here the *structure and state* is the content. Capture what the screen shows and what state controls are in.

```markdown
---
source_type: app_ui
platform: <app name if known>
notes: screen capture of <which screen>
---

## Screen: Settings → Notifications

**Header:** Notifications

Settings shown:
- **Push notifications:** ON
- **Email digest:** OFF
- **Frequency:** Weekly (dropdown)

**Visible data / content:**
[transcribe any list items, cards, values, labels]

**Primary actions available:** Save, Cancel
```

Capture toggle/checkbox states (ON/OFF, checked/unchecked) — they're meaningful. Drop purely decorative chrome.

---

## Data view (tables, spreadsheets, analytics)

Reconstruct tables as Markdown tables. For charts, describe + extract readable values.

```markdown
---
source_type: data_view
---

## Table: Q2 Sales by Region

| Region | Revenue | Growth |
|--------|---------|--------|
| North  | $1.2M   | +12%   |
| South  | $890K   | -3%    |

## Chart: Monthly Active Users
[chart: line chart, Jan–Jun. Values readable: Jan 10k, Feb 14k, Mar 19k, ... Jun 41k. Trend: steady rise.]
Axis labels: x = month, y = MAU
```

If a table's cells are partly cut off, transcribe what's visible and note it in `notes:`.

---

## Generic

When nothing else fits, default to: metadata header → faithful top-to-bottom transcription with whatever structure (headings/lists) the layout implies → `[image: ...]` / `[ui: ...]` markers for non-text elements.
