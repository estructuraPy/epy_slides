---
title: epy_slides — User manual
subtitle: Build presentations in Markdown
author: ANM Ingeniería
date: 2026-06-18
theme: corporate
aspect-ratio: "16:9"
transition: slide
slide-number: true
footer: epy_slides — User manual
---

## Welcome to epy_slides
<!-- layout: section -->

## What you build here
<!-- layout: title-content -->

- Write a deck once, in plain **Markdown**
- See a live **reveal.js** preview as you type
- Export the same source to **PDF**, **HTML** and **PowerPoint**

::: {.callout-note title="One source, three formats"}
Everything in this manual is itself an epy_slides deck. Open it from
*Help ▸ User manual* at any time.
:::

## The editor at a glance
<!-- layout: image-caption -->

![The Markdown editor (left) and the live deck preview (right)](__SHOT_EDITOR__){width=78%}

## The toolbar, left to right
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### Slides
Insert a new slide from a layout, or a blank slide break.
:::
::: {.card}
#### Content
Bullets, columns, quotes, images, tables, equations, code, callouts,
diagrams and speaker notes.
:::
::: {.card}
#### Export
PDF, HTML and PowerPoint — plus the live theme and language switches in
*View*.
:::
::::

## Writing slides
<!-- layout: title-content -->

- A line that starts with `## ` begins a **new slide**
- A single `# ` begins a **section divider**
- A comment such as `<!-- layout: two-column -->` picks the slide layout

::: {.callout-tip title="Keep it plain"}
You never leave Markdown. Every menu just drops the right text at the cursor.
:::

## The New Slide dialog
<!-- layout: image-caption -->

![Slides ▸ New slide — pick a layout, type a title, optionally add an image](__SHOT_NEW_SLIDE__){width=42%}

## The layouts you can pick
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### Structure
Section · Title + bullets · Two columns · Comparison · Blank
:::
::: {.card}
#### Imagery
Image + caption · Full-bleed · Image left · Image right · Quote + portrait
:::
::: {.card}
#### Emphasis
Big numbers · Agenda · Cards · Timeline · Quote · Code
:::
::::

## Design components
<!-- layout: big-stat -->

:::: {.stats}
::: {.stat}
**16**

[slide layouts]{.stat-label}
:::
::: {.stat}
**9**

[colour themes]{.stat-label}
:::
::: {.stat}
**3**

[export formats]{.stat-label}
:::
::::

## A timeline, for example
<!-- layout: timeline -->

::: {.timeline}
- **Write** — type Markdown, watch the preview
- **Design** — pick a layout and a theme
- **Export** — PDF, HTML or PowerPoint
:::

## Figures, tables and equations
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Figure**

![Content ▸ Image / Figure](__SHOT_FIGURE__){width=92%}
:::
::: {.column width="50%"}
**Table**

![Content ▸ Table](__SHOT_TABLE__){width=88%}
:::
::::

## Equations render with MathJax
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="46%"}
![Content ▸ Equation](__SHOT_EQUATION__){width=98%}
:::
::: {.column width="54%"}
For a slender tower, wind pressure governs:

$$ q = \tfrac{1}{2}\,\rho\,V^{2} $$

In PowerPoint, equations export as images.
:::
::::

## Diagrams, two engines
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Mermaid** — flowcharts

```mermaid
flowchart TD
    A[Write] --> B[Design]
    B --> C[Export]
```
:::
::: {.column width="50%"}
**nomnoml** — UML-style

```nomnoml
[Deck] -> [Slide]
[Slide] -> [Block]
```
:::
::::

::: {.notes}
Both diagram engines read the active theme's colours, so a diagram always
matches the deck. They render in HTML and PDF; in PowerPoint they fall back
to their source text.
:::

## Themes
<!-- layout: image-caption -->

![View ▸ Theme switches all nine palettes; New theme… opens the editor](__SHOT_THEME_EDITOR__){width=46%}

## Presentation properties
<!-- layout: image-caption -->

![Presentation ▸ Presentation properties — title, footer, logo and watermark](__SHOT_PROPERTIES__){width=44%}

## Logo and watermark travel with the deck
<!-- layout: title-content -->

- A picked **logo** or **watermark** is copied into the deck's `figures/`
  folder, so the deck stays portable
- The watermark shows faintly behind every slide and is stamped into the PDF
- The preview repaints the moment you accept the dialog

## Exporting
<!-- layout: cards -->

:::: {.cards}
::: {.card}
#### PDF
One slide per landscape page, with metadata and the watermark stamped in.
:::
::: {.card}
#### HTML
A continuous, scrollable web page — natural to share as a link.
:::
::: {.card}
#### PowerPoint
Standard slide layouts with the theme's colours, fonts and speaker notes.
:::
::::

## Present and share
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Present**

- Arrow keys navigate
- `S` opens speaker notes
- `F` goes full screen
:::
::: {.column width="50%"}
**Share**

- Export to HTML for the web
- Export to PDF to print
- Export to PPTX for PowerPoint
:::
::::

## You are ready
<!-- layout: quote -->

> The best presentation is the one you can keep editing as plain text.
>
> — ANM Ingeniería
