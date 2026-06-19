---
title: Welcome to epy_slides
subtitle: Build presentations in Markdown
author: ANM Ingeniería
date: 2026-06-18
theme: corporate
aspect-ratio: "16:9"
transition: slide
slide-number: true
footer: epy_slides — ANM Ingeniería
---

## Getting started
<!-- layout: section -->

## What is epy_slides?
<!-- layout: title-content -->

- Write slides in plain **Markdown**
- See a live **reveal.js** preview on the right
- Export to **PDF**, **HTML** and **PowerPoint**
- One source, three formats

## One source, many layouts
<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
**Author**

- `## ` starts a new slide
- Use the *Slides* menu for layouts
- Use the *Content* menu for blocks
:::
::: {.column width="50%"}
**Present**

- Arrow keys navigate
- `S` opens speaker notes
- `F` goes full screen
:::
::::

## Math and code
<!-- layout: title-content -->

Equations render with MathJax:

$$ E = mc^2 $$

```python
def greet(name):
    return f"Hello, {name}!"
```

## Callouts and notes
<!-- layout: title-content -->

::: {.callout-note title="Tip"}
Pick a theme from *View ▸ Theme* — the preview and every export update.
:::

::: {.notes}
These speaker notes appear in the presenter view and in PowerPoint,
but never on the slide itself.
:::

## A closing thought
<!-- layout: quote -->

> The best presentation is the one you can keep editing as plain text.
>
> — ANM Ingeniería
