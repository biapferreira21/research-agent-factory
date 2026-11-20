# Worked Examples

These illustrate the transformation. Each shows what the screenshot contains and the ideal Markdown output. Study the *decisions*, not just the format.

---

## Example 1: A tweet with engagement and a quote-tweet

**What the screenshot shows:** An X post by a verified user, with a quote-tweet embedded, a navigation sidebar on the left, a "trending" rail on the right, and a compose box at the bottom.

**Good output:**

```markdown
---
source_type: social_post
platform: X
captured: not visible
---

## Post

**Author:** Sara Lin (@saralin) · Verified
**Posted:** 5h

> Shipping > planning. Spent a year designing the perfect roadmap. Threw it out in week 2 once real users showed up. Build, watch, adjust.

**Engagement:** 4.1K likes · 612 reposts · 203 replies · 180K views

**Quoted post:**
> **@devhabits:** What's the one habit that made you a better engineer?
```

**Decisions:** The left nav, trending rail, and compose box are chrome — dropped. The quote-tweet is content — kept and nested. Engagement counts kept (they signal reach). Nothing summarized.

---

## Example 2: A Reddit thread

**What the screenshot shows:** A post title, body, and three nested comments with vote counts; plus the subreddit header, an award icon row, and a "Join" button.

**Good output:**

```markdown
---
source_type: thread
platform: Reddit
---

## r/selfhosted — "Finally ditched Google Photos — here's my setup"

**OP:** u/homelab_hannah · 1.4k upvotes · 8h
> Running Immich on a mini PC with a 4TB drive. Backs up to a second drive nightly. Phone uploads automatically. Took a weekend to set up, zero regrets.

### Comments

- **u/skeptic_steve** (210 pts): How's the face recognition compared to Google?
  - **u/homelab_hannah** (156 pts): Surprisingly good now. Not quite parity but close, and it's all local.
    - **u/skeptic_steve** (44 pts): Sold. Setting it up this weekend.
- **u/backup_betty** (98 pts): Please tell me you have an offsite backup too. RAID is not a backup.
```

**Decisions:** Subreddit header kept as the section title (orientation). Award icons and the Join button dropped. Vote counts kept. Nesting mirrors the reply tree.

---

## Example 3: A mobile app settings screen

**What the screenshot shows:** iOS status bar (battery, time, signal), a "Notifications" settings screen with three toggles and a dropdown, and a bottom tab bar.

**Good output:**

```markdown
---
source_type: app_ui
platform: unknown iOS app
notes: Notifications settings screen
---

## Screen: Notifications

Settings shown:
- **Allow Notifications:** ON
- **Sounds:** OFF
- **Badges:** ON
- **Notification grouping:** Automatic (dropdown)

**Primary actions available:** back navigation only
```

**Decisions:** Status bar and tab bar are chrome — dropped. Toggle states are the actual content — captured precisely. No invented app name; marked unknown.

---

## Example 4: When text is partly unreadable

If part of the image is blurry or cut off, don't guess:

```markdown
> Our Q3 numbers came in at $[?]M, up [illegible]% over last quarter.
```

And note it in the header:

```markdown
notes: bottom-right of image is blurry; revenue figure and growth % uncertain
```

This honesty is what makes the output trustworthy as LLM context — a confidently wrong number is worse than a flagged gap.

---

## Example 5: Design mode — cloning a recipe site's look

**What the screenshot shows:** A clean recipe landing page — serif display headline, a row of food-photo cards on light grey, one warm orange CTA, a text nav with a theme toggle.

**Request signal:** "build a landing page that looks like this" → design mode.

**Good output:**

```markdown
---
mode: design_spec
source: Julienne
platform: web
theme: light
---

# Design Spec: Julienne

## Character
Clean, editorial, warm-minimal. Light mode, very airy, magazine feel from a serif display face paired with a neutral sans UI. One warm accent does all the work.

## Color palette
| Role | Hex (est.) | Usage |
|------|-----------|-------|
| Background | #FFFFFF | page |
| Card surface | #F5F4F2 | recipe cards (warm grey) |
| Primary text | #1A1A1A | headings, body |
| Muted text | #8A8A8A | sub-headline, "By @handle" |
| Accent | #D4622A | primary CTA, active states |
| Border | #EAEAEA | header line, outlines, cards |

## Typography
- **Display / H1:** elegant serif (similar to Playfair Display / GT Super), regular, large; italic serif for emphasis words.
- **Nav / body / buttons:** neutral sans (similar to Inter / system-ui), regular–medium.
- **Card titles:** serif, ~16–18px.
- Signature: serif-display ↔ sans-UI contrast.

## Layout & spacing
- Centered hero above a full-width 5-column card grid.
- Generous vertical rhythm; base unit ~8px; ~16px gaps between cards.
- Hero narrow/centered; cards left-aligned internally.

## Components
- **Primary button:** solid #D4622A, white label, ~10px radius, ~12px×20px padding, leading icon.
- **Secondary button:** white fill, peachy outline, dark label, same size.
- **Cards:** #F5F4F2, ~12px radius, flat (no shadow), ~16px padding; title + bookmark icon top, centered photo, muted "By @handle" footer.
- **Header:** white, thin bottom border, logo left, text nav right, circular theme toggle.

## Imagery & icons
- **Images:** top-down food photos on colored plates, centered on the grey card (not full-bleed), ~square.
- **Icons:** thin line style (similar to Lucide/Feather).

## Distinctive details
- Serif-display + sans-UI pairing — don't go all-sans or it loses character.
- Single terracotta accent on an otherwise black/white/warm-grey palette.
- Flat grey cards with floating top-down photos, no shadows.

## Implementation hint
Tailwind: white bg, rounded-xl flat grey cards (no shadow), generous py-24 hero, Playfair Display headings + Inter UI, single terracotta accent (#D4622A), thin Lucide icons.
```

**Decisions:** Every color carries a role, not just a value. Fonts name a recognizable substitute plus the classification, so the dev isn't stuck. The "distinctive details" and "implementation hint" are what turn a generic clone into a faithful one — they're the highest-leverage part. Every hex is flagged as an estimate; for exact color, the dev confirms with a picker.
