# epy_slides

**Markdown slide editor** with a live **reveal.js** preview and one-click export
to **PDF**, **HTML** and **PowerPoint**. Write your deck in plain Markdown; get a
themed presentation. A standalone GUI of the **ePy Suite**.

Author: Ing. Angel Navarro-Mora M.Sc. — ANM Ingeniería. License: MIT.

## Highlights

- **One source, three formats.** The same Markdown renders to a reveal.js deck
  (preview + HTML), a paginated PDF, and a native `.pptx`.
- **Predefined slide layouts.** A *New Slide* picker inserts ready-made
  skeletons (section, title + bullets, two columns, comparison, image, quote,
  code, blank) — each shown with a small preview thumbnail.
- **Block-based content.** Insert bullet lists (with incremental reveals), two
  columns, quotes, speaker notes, images, tables, LaTeX equations, code and
  callouts from dialogs.
- **Themes.** Nine bundled themes plus a theme editor, browsable in a preview
  gallery (*View ▸ Theme ▸ Browse themes…*); the active theme styles the
  preview and every export.
- **Bilingual UI** (English / Spanish), switchable live.
- **Citations.** Link a `.bib` file, write `[@key]` inline, choose
  IEEE / APA / Chicago from *References*; a References slide is appended
  automatically.

## Writing a deck

Slides are separated by level-2 headings; the leading YAML block configures the
deck:

```markdown
---
title: My talk
author: ANM Ingeniería
theme: corporate
aspect-ratio: "16:9"
---

## First slide

- a point
- another point

## Two columns
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
Left
:::
::: {.column width="50%"}
Right
:::
::::
```

Speaker notes (`::: {.notes} … :::`) show in the presenter view and in
PowerPoint, never on the slide. Equations use `$…$` / `$$…$$`.

## Install

Download the latest installer from the
[Releases page](https://github.com/estructuraPy/epy_slides/releases/latest):

- **Windows:** `epy_slides-setup-*.exe` (per-user, no admin required).
- **Ubuntu:** `epy-slides_*.deb` — `sudo apt install ./epy-slides_*.deb`.

### From source

```bash
pip install -e .
epy_slides
```

Requires Python ≥ 3.10. Pandoc is bundled via `pypandoc-binary`.

## Export notes

- **PDF** uses reveal.js print mode (one slide per landscape page) and embeds
  the document metadata and copyright notice.
- **PowerPoint** is produced by Pandoc using a per-theme reference deck. Some
  reveal-only features (transitions, fragments, full-bleed backgrounds) do not
  carry into `.pptx`; equations are rasterised and callouts become blockquotes.

## Credits

reveal.js (MIT) and MathJax are bundled. Built with PySide6; PDF stamping uses
pypdf, reportlab and Pillow.
