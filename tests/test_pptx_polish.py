"""PPTX export: slide size follows the deck and dense text fits its frame."""

from __future__ import annotations

import re
import zipfile
from xml.etree import ElementTree as ET

import pytest

from epy_slides._core._pptx_polish import (
    _estimate_scale,
    polish_pptx,
)
from epy_slides._core.renderer import _resolve_reference_pptx, export_pptx

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"

_DENSE = "\n".join(
    f"- Bullet {i} with a reasonably long sentence that wraps across the "
    "line and keeps adding words to force real overflow in the frame"
    for i in range(1, 15)
)

_DECK = f"""---
title: Overflow probe
theme: corporate
---

## Dense bullet slide

{_DENSE}

## Short slide

- Just one line
"""


def _autofits(pptx_path, slide: str) -> list[str]:
    with zipfile.ZipFile(pptx_path) as z:
        xml = z.read(f"ppt/slides/{slide}.xml").decode()
    return re.findall(r"<a:normAutofit[^>]*/>", xml)


def _slide_size(pptx_path) -> str:
    with zipfile.ZipFile(pptx_path) as z:
        pres = z.read("ppt/presentation.xml").decode()
    match = re.search(r"<p:sldSz[^>]*/>", pres)
    assert match is not None
    return match.group(0)


@pytest.fixture(scope="module")
def deck_169(tmp_path_factory):
    out = tmp_path_factory.mktemp("pptx") / "deck.pptx"
    export_pptx(_DECK, out)
    return out


def test_dense_slide_gets_computed_font_scale(deck_169):
    fits = _autofits(deck_169, "slide2")
    scales = [
        int(m.group(1))
        for fit in fits
        if (m := re.search(r'fontScale="(\d+)"', fit))
    ]
    assert scales, "dense body must carry a computed fontScale"
    assert all(s < 100000 for s in scales)
    assert all(s >= 40000 for s in scales)


def test_short_slide_gets_plain_autofit_only(deck_169):
    fits = _autofits(deck_169, "slide3")
    assert fits, "every content placeholder gets shrink-on-overflow"
    assert all("fontScale" not in fit for fit in fits)


def test_titles_are_not_scaled(deck_169):
    with zipfile.ZipFile(deck_169) as z:
        xml = z.read("ppt/slides/slide2.xml").decode()
    title_block = xml.split("</p:sp>")[0]
    assert 'type="title"' in title_block
    fit = re.search(r"<a:normAutofit[^>]*/>", title_block)
    assert fit is not None
    assert "fontScale" not in fit.group(0)


def test_default_deck_is_widescreen_without_stale_type(deck_169):
    tag = _slide_size(deck_169)
    assert 'cx="12192000"' in tag
    assert 'cy="6858000"' in tag
    assert "type=" not in tag


def test_four_three_deck_uses_four_three_canvas(tmp_path):
    deck = _DECK.replace("---\n\n##", 'aspect-ratio: "4:3"\n---\n\n##', 1)
    out = tmp_path / "deck43.pptx"
    export_pptx(deck, out)
    tag = _slide_size(out)
    assert 'cx="9144000"' in tag
    assert 'cy="6858000"' in tag


def test_reference_picker_prefers_aspect_variant():
    wide = _resolve_reference_pptx("corporate", "16:9")
    narrow = _resolve_reference_pptx("corporate", "4:3")
    assert wide is not None and wide.name == "corporate.pptx"
    assert narrow is not None and narrow.name == "corporate_43.pptx"


def test_estimator_scales_long_text_and_keeps_short():
    body = ET.fromstring(
        f'<p:txBody xmlns:p="http://schemas.openxmlformats.org/'
        f'presentationml/2006/main" xmlns:a="{_A}">'
        + "".join(
            f"<a:p><a:r><a:t>{'x' * 120}</a:t></a:r></a:p>" for _ in range(12)
        )
        + "</p:txBody>"
    )
    frame = (10972800, 4525963)
    sizes = [2200] * 9
    assert _estimate_scale(body, frame, sizes) < 1.0

    short = ET.fromstring(
        f'<p:txBody xmlns:p="http://schemas.openxmlformats.org/'
        f'presentationml/2006/main" xmlns:a="{_A}">'
        "<a:p><a:r><a:t>one line</a:t></a:r></a:p></p:txBody>"
    )
    assert _estimate_scale(short, frame, sizes) > 1.0


def test_polish_is_noop_on_deck_without_slides(tmp_path):
    empty = tmp_path / "empty.pptx"
    with zipfile.ZipFile(empty, "w") as z:
        z.writestr("docProps/app.xml", "<x/>")
    polish_pptx(empty)  # must not raise
    with zipfile.ZipFile(empty) as z:
        assert z.namelist() == ["docProps/app.xml"]


_MATH_TABLE_DECK = """---
title: Math-in-table probe
theme: corporate
---

## Table with math

| Variable | Símbolo |
|---|---|
| Temperatura | $T$ |
| Humedad relativa | $Hr$ |
"""


def test_math_in_table_cell_gets_declared_namespace(tmp_path):
    """Pandoc wraps table-cell math in <a14:m> without declaring xmlns:a14;
    polish must repair the part instead of crashing, and the shipped deck
    must parse as strict XML."""
    out = tmp_path / "math_table.pptx"
    export_pptx(_MATH_TABLE_DECK, out)  # polish runs inside export
    with zipfile.ZipFile(out) as z:
        slides = [
            n
            for n in z.namelist()
            if re.match(r"ppt/slides/slide\d+[.]xml$", n)
        ]
        assert slides
        for name in slides:
            data = z.read(name)
            ET.fromstring(data)  # must not raise: every prefix declared
            text = data.decode()
            if "<a14:m>" in text:
                assert "xmlns:a14=" in text


def test_ensure_declared_ns_repairs_and_is_noop_when_clean():
    from epy_slides._core._pptx_polish import _ensure_declared_ns

    broken = (
        b'<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main">'
        b"<a14:m>x</a14:m></p:sld>"
    )
    repaired, changed = _ensure_declared_ns(broken)
    assert changed is True
    ET.fromstring(repaired)

    clean, changed2 = _ensure_declared_ns(repaired)
    assert changed2 is False
    assert clean == repaired


def test_ensure_declared_ns_ignores_later_inline_declaration():
    """A later inline xmlns:a14 does NOT cover an earlier <a14:m>: the repair
    must still declare the prefix on the root."""
    from epy_slides._core._pptx_polish import _ensure_declared_ns

    broken = (
        b'<p:sld xmlns:p="http://schemas.openxmlformats.org/'
        b'presentationml/2006/main">'
        b"<a14:m>x</a14:m>"
        b'<other xmlns:a14="http://schemas.microsoft.com/office/'
        b'drawing/2010/main" />'
        b"</p:sld>"
    )
    repaired, changed = _ensure_declared_ns(broken)
    assert changed is True
    ET.fromstring(repaired)
