# Example deck — The Empire State Building

A feature-complete epy_slides deck about the Empire State Building, mirroring
the `newmark` example from epy_reports but built for **presentations**.

## Files

- `empire_state_building.md` — the deck source (English). Exercises the full feature
  set: a section divider, a numbered **agenda**, a **big-numbers** stat row,
  a **cards** grid, a vertical **timeline**, title + bullets, two-column and
  labelled **comparison** layouts, an **image-left** split, a display
  equation, a titled callout, a code block, speaker notes, a **quote +
  portrait** layout and a closing quote. It also draws the load path twice —
  once with a **Mermaid** flowchart and once with a **nomnoml** component
  diagram — both auto-themed to match the active palette. Front matter sets
  the theme, 16:9 aspect ratio, footer, slide numbers, a grayscale watermark
  and a copyright notice.
- `empire_state_building_es.md` — the same deck in Spanish (full translation,
  same layouts, assets and front matter).
- `esb_skyline.png` — a simple stepped-tower silhouette used both as the image
  slide and as the watermark.
- `render_all_themes.py` — renders the deck once per theme to **HTML**
  (continuous scroll), **PPTX** (Pandoc + per-theme reference deck) and **PDF**
  (reveal.js print mode, one slide per landscape page).

## Render it

```bash
python render_all_themes.py            # every theme
python render_all_themes.py corporate  # a single theme
```

Output is written to `_render/themes/` (git-ignored). The PDF step drives Qt
WebEngine; on a headless machine set `QT_QPA_PLATFORM=offscreen`. Both languages
are rendered: English files are `empire_state_<theme>.*`, Spanish files carry an
`_es` suffix (`empire_state_<theme>_es.*`).

## What it demonstrates

One Markdown source, three formats:

- The **HTML** export is a standalone reveal.js slideshow — arrow keys
  navigate, `F` goes full screen, `S` opens the speaker view — so it presents
  like a deck when shared as a link.
- The **PDF** keeps the slide pagination (one slide per page) for printing.
- The **PPTX** opens in PowerPoint with the standard slide layouts and the
  theme's colours and fonts. Mermaid/nomnoml diagrams are rasterized to themed
  images and the design components become native tables/blocks, so the slides
  keep their look; the display equation is the one element the PowerPoint
  writer renders as text.

## Languages / Idiomas

The deck ships in **English** (`empire_state_building.md`) and **Spanish**
(`empire_state_building_es.md`), following the repo convention (`<name>.md`
English, `<name>_es.md` Spanish). `render_all_themes.py` renders both.

## Disclaimer / Aviso

This example is provided **for demonstration purposes only**. Its content
(historical, technical and numerical) is illustrative and has not been reviewed
in detail; it must not be used as a basis for engineering or any other
decisions. Provided as is, without warranty of any kind.

Este ejemplo se proporciona **únicamente con fines demostrativos**. Su contenido
(histórico, técnico y numérico) es ilustrativo y no ha sido revisado en detalle;
no debe usarse como base para decisiones de ingeniería ni de ningún otro tipo.
Se entrega tal cual, sin garantía de ningún tipo.
