# Changelog

All notable changes to `epy_slides` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- **Watermark stays visible on every slide.** The on-screen watermark now
  adapts to the deck background (a `multiply` blend on light themes, `screen`
  + invert on dark ones) and uses a `difference` blend on full-bleed image
  slides, so it no longer washes out over photos or dark backgrounds. The
  default opacity rose from 0.07 to 0.12.
- **Big-number slides keep fitting.** The `big-stat` figures shrink as more
  stats share the row (smaller for 4 and 5 columns) and no longer wrap
  mid-value, so three to five large numbers stay on one legible line.

### Changed
- **Adjustable slide margin.** A `margin:` front-matter key (set from
  *Presentation properties ▸ Margin*) controls the reveal margin fraction;
  the default rose from 0.04 to 0.06 for more breathing room.
- **HTML export is now continuous.** The deck renders as a reveal.js scroll
  view — one continuous scrollable page — instead of a click-through
  slideshow. The PDF and PowerPoint exports keep their per-slide pagination.

### Added
- **Citation / bibliography support.** Link a `.bib` file from
  *References ▸ Link bibliography*, insert citations with `[@key]` or
  via *Insert citation…*, choose IEEE / APA / Chicago style. A References
  slide is appended automatically when the deck declares `bibliography:`.
- **Slide-layout previews.** The *New slide* picker shows a small schematic
  preview of every layout, so you choose the structure at a glance, not just
  by its name.
- **Theme gallery** (*View ▸ Theme ▸ Browse themes…*) — every theme as a live
  colour/typography preview swatch, custom themes included.
- `examples/empire_state_building/` — a feature-complete demo deck (every
  layout and content block) with a `render_all_themes.py` harness that
  exports HTML + PPTX + PDF per theme.

## [0.1.0] — 2026-06-18

Initial release. `epy_slides` is a desktop Markdown slide editor: one Markdown
source renders live as a reveal.js deck and exports to PDF, HTML and PowerPoint.

### Authoring
- Multi-tab editor (PySide6) with a live **reveal.js** preview; slides are
  separated by `## ` headings.
- **New Slide** layout picker (*Slides ▸ New slide…*) with predefined layouts:
  section divider, title + bullets, two columns, comparison, image + caption,
  full-bleed image, quote, code and blank.
- **Content** blocks inserted from dialogs: bullet list (optionally revealed
  incrementally), two columns, quote, speaker notes, image, figure, table,
  LaTeX equation, code block, callouts and checklist.
- **Presentation properties** form writes the YAML front matter (title block,
  theme, aspect ratio, transition, slide numbers, footer, logo, watermark,
  copyright).

### Export
- **PDF** via reveal.js print mode — one slide per landscape page (16:9 or 4:3),
  with the document metadata and copyright embedded and an optional grayscale
  watermark.
- **HTML** — a single self-contained reveal.js file that works offline.
- **PowerPoint (.pptx)** via Pandoc, with a per-theme reference deck so the
  exported slides carry the theme's colours and fonts.

### Appearance
- Nine bundled themes plus a **theme editor** for custom ones; the active theme
  drives the preview and every export.
- Bilingual interface (English / Spanish), switchable live from
  *View ▸ Language*.
- Appearance **templates** capture theme + aspect ratio + transition + footer +
  logo + watermark + copyright for reuse.

### Packaging
- Windows (`.exe`, per-user) and Ubuntu (`.deb`, PEP 668-safe virtualenv)
  installers, with a CI workflow that publishes a GitHub Release on a `v*` tag.
- reveal.js (MIT) and MathJax are bundled; PDF stamping uses pypdf + reportlab +
  Pillow (no AGPL dependencies).
