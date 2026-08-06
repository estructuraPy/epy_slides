# Changelog

All notable changes to `epy_slides` are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] — 2026-08-05

### Fixed
- **PowerPoint slides no longer overflow.** Pandoc emits every
  placeholder without autofit, so dense slides silently spilled past
  the frame. Exported decks are now post-processed: every content
  placeholder gets "shrink text on overflow", and when the text
  measurably exceeds the frame it inherits from the layout/master, a
  computed `fontScale` is stored so the deck opens already fitting
  (Office only recalculates autofit on edit, not on open).
- **PPTX typography matches the live preview.** The reference decks
  shipped Office's print-era defaults (32/28/24 pt body, 44 pt title),
  which filled the frame after a few bullets; they now carry the
  preview's proportions (22/20/18 pt body, 36 pt title), so an exported
  slide holds comparable content to the on-screen one.
- The reference-deck generator wrote its output into a ghost
  `src/src/` tree (stale path from before it became a package);
  regenerated references now actually ship.

### Added
- **4:3 PowerPoint export.** A deck with `aspect-ratio: "4:3"` now
  exports on a true 10 x 7.5 in canvas (a per-theme `_43` reference
  variant); it always came out 16:9 widescreen before.

## [0.2.1] — 2026-08-05

### Fixed
- **PDF links now navigate.** The deck's exported PDF kept its link
  annotations but internal ones were dead: the widescreen scaling pass
  and the watermark stamping rebuilt the document through a fresh
  writer, dropping the named destinations the links point at. Both now
  clone the document instead, so links in the PDF work.

## [0.2.0] — 2026-08-05

### Fixed
- **External links in the deck.** The deck forces external links to
  `target="_blank"`, but the preview swallowed those popups entirely —
  clicking a web link did nothing. They now open in the system browser.
- **Internal slide links.** With the deck's `<base href>`, an internal
  link (`#/2` or `#slide-id`) resolved against the base and navigated
  the preview away. An injected interceptor now drives the reveal deck
  directly (`Reveal.slide`), for routes and named anchors alike.

### Added
- **Back/Forward across slide jumps.** Every link jump lands in
  `location.hash`, so `Alt+Left` / `Alt+Right` (and the context menu)
  walk the jump history back to the slide you left; re-renders no longer
  pollute the history.

## [0.1.10] — 2026-08-05

### Fixed
- **Qt startup crash in conda environments (Windows).** The package now
  pins the System32 ICU at import time (`_pin_system_icu`), preventing
  `ImportError: DLL load failed ... (WinError 127)` when conda's
  `Library\bin` ICU shadows the Windows one Qt links against.
- **Test-suite shutdown crash.** The session teardown now flushes queued
  `deleteLater()` deletions and destroys leftover widgets and the
  `QApplication` while the interpreter is healthy; zombie WebEngine
  previews no longer crash Qt's native teardown (0xC0000005) after all
  tests pass.

## [0.1.8] — 2026-06-24

### Fixed
- **Dense slides fit in the browser too, not just the PDF.** The shrink-to-fit
  pass measured overflow against the section's height, which on screen grows to
  fit the content (unlike the pinned print pages), so content-heavy slides were
  still clipped in the live preview and the standalone HTML deck. It now
  measures against the configured slide height and re-fits on reveal's `ready`
  event, so dense slides scale to fit on screen as well as in the PDF.

## [0.1.7] — 2026-06-24

### Fixed
- **Full-bleed cover images now reach PowerPoint.** A slide whose background is
  set with `{background-image="…"}` previously lost its picture in the `.pptx`
  export (the reveal background was dropped). The image is now re-added as an
  inline picture so the PowerPoint slide carries it too.

## [0.1.6] — 2026-06-24

### Added
- **Empire State example: integrated illustrations.** The Empire State deck now
  weaves seven themed illustrations through the story — a full-bleed cover, two
  captioned scene slides, the Art Deco tower beside the massing notes, a serene
  skyline next to the architect's quote, and a two-image style gallery —
  generated with LitoClaw. Both languages carry the image credit.

### Fixed
- **Legible titles over full-bleed images.** A title on an `image-fullbleed`
  slide now sits on a translucent plate with light text and a drop shadow, so it
  stays readable over any photograph and in any theme.

## [0.1.5] — 2026-06-24

### Fixed
- **Dense slides no longer clip.** Content taller than the fixed slide frame
  (e.g. multi-card layouts) was silently cut off at the bottom in both the live
  preview and the PDF export. A shrink-to-fit pass now scales any overflowing
  slide down to fit, leaving slides that already fit untouched. It runs after
  layout, on slide change and resize, when the PDF print pages are built
  (`pdf-ready`), and after MathJax typesets (which changes heights).
- **Empire State example wording.** The "410 days" figure is now described as
  construction time (from the March 1930 steel start), not the span from the
  January 1930 excavation to opening (~15 months).

## [0.1.4] — 2026-06-23

### Added
- **Insert ▸ Disclosure.** A typed disclosure note — AI assistance, document
  integrity, confidentiality or draft — inserted from the *Content ▸ Disclosure*
  submenu and styled by the theme. The example deck now carries an AI-use
  disclosure inserted with this block.

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
