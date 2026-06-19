# Example deck — The Empire State Building

A feature-complete epy_slides deck about the Empire State Building, mirroring
the `newmark` example from epy_mdr but built for **presentations**.

## Files

- `empire_state_building.md` — the deck source. Exercises every slide layout
  and content block: a section divider, title + bullets, a two-column
  comparison, a display equation, a titled callout, an image slide, a code
  block, speaker notes and a quote. Front matter sets the theme, 16:9 aspect
  ratio, footer, slide numbers, a grayscale watermark and a copyright notice.
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
WebEngine; on a headless machine set `QT_QPA_PLATFORM=offscreen`.

## What it demonstrates

One Markdown source, three formats:

- The **HTML** export is a continuous, scrollable web page — not a click-through
  slideshow — so it reads naturally when shared as a link.
- The **PDF** keeps the slide pagination (one slide per page) for printing.
- The **PPTX** opens in PowerPoint with the standard slide layouts and the
  theme's colours and fonts.
