import tempfile
import zipfile
from pathlib import Path

from epy_slides.renderer import export_pptx

_DECK = """---
title: Deck
theme: corporate
---

## One

- a
- b

## Two

<!-- layout: two-column -->

:::: {.columns}
::: {.column width="50%"}
Left
:::
::: {.column width="50%"}
Right
:::
::::
"""


def test_export_pptx_is_valid_package():
    out = Path(tempfile.mkdtemp()) / "deck.pptx"
    export_pptx(_DECK, out, theme_id="corporate")
    assert zipfile.is_zipfile(out)
    names = zipfile.ZipFile(out).namelist()
    assert "ppt/presentation.xml" in names
    slides = [
        n
        for n in names
        if n.startswith("ppt/slides/slide") and n.endswith(".xml")
    ]
    assert len(slides) >= 2


def test_export_pptx_falls_back_without_reference():
    out = Path(tempfile.mkdtemp()) / "deck.pptx"
    export_pptx(_DECK, out, theme_id="does-not-exist")
    assert zipfile.is_zipfile(out)
