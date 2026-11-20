# Design Spec Extraction

This is the heart of **design mode**. The output is a design spec precise enough that an LLM can rebuild the look without the image. Think like a developer writing down a design system from a reference, not like someone describing a picture.

Core principle: **be specific and actionable, and label every estimate as an estimate.** "Blue button" is useless. "Primary button: solid `#2563EB` (est.), white label, ~8px radius, ~12px×20px padding, medium-weight sans" is buildable.

## Extraction checklist

Work through these in order. Skip nothing that's visible; mark what you can't determine.

### 1. Overall character
One or two sentences capturing the vibe so the LLM sets the right tone before details: minimal / brutalist / playful / corporate / editorial / techy; light or dark mode; information density (airy vs dense); any era cue (retro, Web 1.0, glassmorphism, neo-brutalism, etc.).

### 2. Color palette
List every distinct color with a hex **estimate** and its **role + usage**. Don't skip greys — they define the feel. Typical roles:
- Page background
- Surface / card background
- Primary text
- Secondary / muted text
- Primary accent / brand (CTAs, links)
- Secondary accent (if any)
- Borders / dividers
- Status colors (success / warning / error) if present

Format as a table. Note when colors are used on what (e.g. "accent only on the primary CTA and active nav item").

### 3. Typography
For each text role, give font **classification** + a **named family or close substitute** + relative weight/size. Roles: display/H1, section headings, body, captions/labels, buttons, monospace (if any).
- If you recognize the typeface, name it (e.g. "looks like Söhne / Inter / a Didone serif").
- If not, give a confident, implementable substitute and the classification: "geometric sans-serif, similar to Inter, Geist, or system-ui".
- Note distinctive treatments: tight letter-spacing on headings, all-caps labels, italic accents, large display sizes.

### 4. Spacing & layout
- Layout system: single centered column / sidebar + content / card grid / hero + sections / split. State column count for grids.
- Spacing rhythm: tight or generous; estimate a base unit (commonly 4px or 8px) and whether spacing feels like multiples of it.
- Container: full-bleed vs max-width centered; rough content width feel (narrow reading column vs wide app shell).
- Alignment: left / centered; symmetry.

### 5. Components
For each recurring component, give its style so it can be rebuilt. Buttons deserve the most detail.
- **Buttons**: shape, corner radius, fill vs outline vs ghost, color, label weight, padding, icon usage. Capture each variant (primary/secondary).
- **Cards**: radius, border vs shadow (describe the shadow — soft/large/none), padding, internal structure.
- **Inputs / search**: radius, border, fill, placeholder treatment.
- **Nav / header**: layout, sticky feel, item style, active-state treatment.
- **Badges / tabs / chips**: pill vs square, fill, size.

### 6. Imagery & iconography
- Image type: product photography on white, lifestyle photography, 3D renders, illustrations, gradients/abstract, screenshots, or none.
- Treatment: corner radius on images, full-bleed vs contained, aspect ratios, drop shadows, consistent background (e.g. "all product shots on pure white").
- Icons: line/outline vs filled, stroke weight, corner style, size relative to text. Name a matching set if recognizable (e.g. "thin line icons, similar to Lucide/Feather").

### 7. Distinctive details
The fingerprint of the design — what makes a clone recognizable rather than generic: a signature accent, an unusual radius (very round pills vs sharp corners), a specific soft shadow, heavy letter-spacing, a particular grid gap, a gradient, texture/noise, etc. Call these out explicitly; they're the highest-leverage part of the spec.

## Output template

```markdown
---
mode: design_spec
source: <product/site name if known, else "unknown">
platform: <web / iOS / Android / desktop>
theme: <light | dark>
notes: <partial capture, capture-tool watermark, single screen of a larger app, etc.>
---

# Design Spec: <name>

## Character
<1–2 sentences>

## Color palette
| Role | Hex (est.) | Usage |
|------|-----------|-------|
| Background | #FFFFFF | page background |
| Primary text | #111111 | headings, body |
| Muted text | #6B7280 | captions, secondary |
| Accent | #E8622C | primary CTA, active states |
| Border | #E5E7EB | card edges, dividers |

## Typography
- **Display / H1:** <family or substitute>, <classification>, <weight>, large (~Npx feel)
- **Headings:** ...
- **Body:** ...
- **Labels / buttons:** ...
<note distinctive treatments>

## Layout & spacing
- Layout: <system>
- Spacing: <rhythm + base unit estimate>
- Container: <width feel>
- Alignment: <...>

## Components
- **Primary button:** <shape, radius, fill, color, padding, label>
- **Secondary button:** ...
- **Cards:** <radius, shadow/border, padding>
- **Inputs:** ...
- **Nav / header:** ...
- **Other (badges/tabs):** ...

## Imagery & icons
- **Images:** <type, treatment, aspect ratios>
- **Icons:** <style, weight, matching set>

## Distinctive details
- <signature characteristics that make this design recognizable>

## Implementation hint
<one line a dev can paste, e.g. "Tailwind-friendly: rounded-2xl cards, generous py-24 sections, single accent color, Inter throughout, soft shadows.">
```

The `## Implementation hint` line is optional but valuable — it compresses the whole spec into a directive the LLM can act on immediately.
