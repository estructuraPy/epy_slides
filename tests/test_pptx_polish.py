"""PPTX export: slide size follows the deck and dense text fits its frame."""

from __future__ import annotations

import io
import re
import zipfile
from xml.etree import ElementTree as ET

import pytest

from epy_slides._core._pptx_polish import (
    _apply_autofit,
    _ensure_declared_ns,
    _estimate_scale,
    _para_level,
    _para_text_and_size,
    _ph_key,
    _shape_frame,
    _slide_layout,
    _style_sizes,
    polish_pptx,
)
from epy_slides._core.renderer import _resolve_reference_pptx, export_pptx

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"

_REL_NS_XML = "http://schemas.openxmlformats.org/package/2006/relationships"
_REL_LAYOUT_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006"
    "/relationships/slideLayout"
)
_REL_NOTES_TYPE = (
    "http://schemas.openxmlformats.org/officeDocument/2006"
    "/relationships/notesSlide"
)

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


def _dense_paragraph_xml(count: int) -> str:
    """Build ``<a:p>`` paragraphs dense enough to overflow a tiny frame."""
    words = "word " * 40
    return "".join(
        f"<a:p><a:r><a:t>{words}</a:t></a:r></a:p>"
        for _ in range(count)
    )


def _rels_xml(rel_type: str, target: str) -> str:
    return (
        '<?xml version="1.0"?>'
        f'<Relationships xmlns="{_REL_NS_XML}">'
        f'<Relationship Id="rId1" Type="{rel_type}" '
        f'Target="{target}"/></Relationships>'
    )


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


def test_estimate_scale_returns_one_for_empty_tx_body():
    """A txBody with no <a:p> paragraphs at all has zero measured
    height; treat it as already fitting rather than dividing by
    zero."""
    body = ET.fromstring(
        f'<p:txBody xmlns:p="{_P}" xmlns:a="{_A}"/>'
    )
    assert _estimate_scale(body, (100, 100), [1800] * 9) == 1.0


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


def test_ensure_declared_ns_returns_unchanged_without_sld_root():
    """No <...sld ...> opening tag at all (the root regex finds
    nothing): the input must come back byte-identical instead of
    crashing while trying to locate a root to patch."""
    xml = b"<p:notASlideRoot/>"
    result, changed = _ensure_declared_ns(xml)
    assert changed is False
    assert result == xml


def test_ph_key_returns_none_without_placeholder_element():
    """A shape with no <p:nvPr><p:ph> (e.g. a plain textbox that is
    not tied to any placeholder) yields no placeholder key."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:nvSpPr><p:nvPr/></p:nvSpPr>"
        "<p:spPr/><p:txBody/></p:sp>"
    )
    assert _ph_key(sp) is None


def test_ph_key_returns_type_and_idx_for_placeholder():
    """Counter-example: a shape that declares <p:ph> returns its
    (type, idx) key."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        '<p:nvSpPr><p:nvPr><p:ph type="body" idx="1"/>'
        "</p:nvPr></p:nvSpPr>"
        "<p:spPr/><p:txBody/></p:sp>"
    )
    assert _ph_key(sp) == ("body", "1")


def test_shape_frame_returns_none_for_non_numeric_extents():
    """cx/cy that aren't int-parseable (malformed OOXML) must not
    crash; the shape frame is simply unknown."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        '<p:spPr><a:xfrm><a:ext cx="notanumber" cy="123"/>'
        "</a:xfrm></p:spPr></p:sp>"
    )
    assert _shape_frame(sp) is None


def test_shape_frame_returns_extents_for_valid_frame():
    """Counter-example: numeric cx/cy round-trip as a (cx, cy)
    tuple."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        '<p:spPr><a:xfrm><a:ext cx="100" cy="200"/></a:xfrm>'
        "</p:spPr></p:sp>"
    )
    assert _shape_frame(sp) == (100, 200)


def test_slide_layout_returns_none_without_rels_part():
    """No _rels part for the slide at all: the KeyError from
    zin.read must be swallowed, not propagated."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
    with zipfile.ZipFile(buf) as zin:
        assert _slide_layout(zin, "ppt/slides/slide1.xml") is None


def test_slide_layout_returns_none_for_malformed_rels():
    """A _rels part that fails to parse as XML must not crash the
    lookup; the slide is treated as having no known layout."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
        z.writestr("ppt/slides/_rels/slide1.xml.rels", "<not-closed")
    with zipfile.ZipFile(buf) as zin:
        assert _slide_layout(zin, "ppt/slides/slide1.xml") is None


def test_slide_layout_returns_none_without_layout_relationship():
    """A well-formed rels part with only unrelated relationships
    (e.g. notesSlide) exhausts the loop and returns None."""
    rels = _rels_xml(_REL_NOTES_TYPE, "../notesSlides/notesSlide1.xml")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
        z.writestr("ppt/slides/_rels/slide1.xml.rels", rels)
    with zipfile.ZipFile(buf) as zin:
        assert _slide_layout(zin, "ppt/slides/slide1.xml") is None


def test_slide_layout_returns_target_layout_path():
    """Counter-example: a normal slideLayout relationship resolves
    to the ppt/slideLayouts/... member path, with '../' stripped."""
    rels = _rels_xml(_REL_LAYOUT_TYPE, "../slideLayouts/slideLayout3.xml")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("ppt/slides/slide1.xml", "<p:sld/>")
        z.writestr("ppt/slides/_rels/slide1.xml.rels", rels)
    with zipfile.ZipFile(buf) as zin:
        layout = _slide_layout(zin, "ppt/slides/slide1.xml")
    assert layout == "ppt/slideLayouts/slideLayout3.xml"


def test_style_sizes_returns_empty_without_tx_styles():
    """A slide master with no <p:txStyles> block yields no per-level
    sizes (not defaults) -- callers fall back via styles.get(...)."""
    master = f'<p:sldMaster xmlns:p="{_P}" xmlns:a="{_A}"/>'
    assert _style_sizes(master.encode()) == {}


def test_style_sizes_reads_declared_level_sizes():
    """Counter-example: a master WITH txStyles yields declared
    sizes; levels with no explicit pPr inherit the previous level's
    size."""
    master = (
        f'<p:sldMaster xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:txStyles><p:titleStyle>"
        '<a:lvl1pPr><a:defRPr sz="4400"/></a:lvl1pPr>'
        "</p:titleStyle><p:bodyStyle/><p:otherStyle/>"
        "</p:txStyles></p:sldMaster>"
    )
    styles = _style_sizes(master.encode())
    assert styles["titleStyle"] == [4400] * 9
    assert styles["bodyStyle"] == [1800] * 9


def test_para_level_returns_zero_for_non_numeric_lvl():
    """A pPr lvl attribute that isn't int-parseable falls back to
    the top level rather than crashing."""
    p = ET.fromstring(
        f'<a:p xmlns:a="{_A}"><a:pPr lvl="deep"/></a:p>'
    )
    assert _para_level(p) == 0


def test_para_level_reads_declared_level():
    """Counter-example: a numeric lvl is read normally."""
    p = ET.fromstring(
        f'<a:p xmlns:a="{_A}"><a:pPr lvl="2"/></a:p>'
    )
    assert _para_level(p) == 2


def test_para_text_and_size_falls_back_on_non_numeric_run_size():
    """A run rPr sz that isn't int-parseable falls back to the
    level's default size instead of crashing."""
    p = ET.fromstring(
        f'<a:p xmlns:a="{_A}">'
        '<a:r><a:rPr sz="huge"/><a:t>hello</a:t></a:r>'
        "</a:p>"
    )
    text, size = _para_text_and_size(p, [1800] * 9, 0)
    assert text == "hello"
    assert size == 1800


def test_para_text_and_size_reads_declared_run_size():
    """Counter-example: a numeric run sz overrides the level's
    default size."""
    p = ET.fromstring(
        f'<a:p xmlns:a="{_A}">'
        '<a:r><a:rPr sz="3200"/><a:t>hello</a:t></a:r>'
        "</a:p>"
    )
    text, size = _para_text_and_size(p, [1800] * 9, 0)
    assert text == "hello"
    assert size == 3200


def test_apply_autofit_noop_without_tx_body():
    """A shape with no <p:txBody> at all (e.g. a picture-like
    shape) is left completely untouched instead of crashing."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}"><p:spPr/></p:sp>'
    )
    before = ET.tostring(sp)
    _apply_autofit(sp, 0.5)
    assert ET.tostring(sp) == before


def test_apply_autofit_creates_body_pr_when_absent():
    """A txBody with no <a:bodyPr> yet (not what Pandoc emits, but
    valid OOXML) gets one created and inserted first, then carries
    the computed fontScale/lnSpcReduction for a low scale."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:txBody><a:p/></p:txBody></p:sp>"
    )
    tx_body = sp.find(f"{{{_P}}}txBody")
    assert tx_body.find(f"{{{_A}}}bodyPr") is None

    _apply_autofit(sp, 0.5)

    body_pr = tx_body.find(f"{{{_A}}}bodyPr")
    assert body_pr is not None
    assert list(tx_body)[0] is body_pr
    autofit = body_pr.find(f"{{{_A}}}normAutofit")
    assert autofit is not None
    assert autofit.get("fontScale") == "50000"
    assert autofit.get("lnSpcReduction") == "10000"


def test_apply_autofit_reuses_existing_body_pr():
    """Counter-example: when bodyPr already exists (Pandoc's normal
    output), it is reused in place, not duplicated."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:txBody><a:bodyPr/><a:p/></p:txBody></p:sp>"
    )
    tx_body = sp.find(f"{{{_P}}}txBody")
    original_body_pr = tx_body.find(f"{{{_A}}}bodyPr")

    _apply_autofit(sp, 1.0)

    assert len(tx_body.findall(f"{{{_A}}}bodyPr")) == 1
    assert tx_body.find(f"{{{_A}}}bodyPr") is original_body_pr
    autofit = tx_body.find(f"./{{{_A}}}bodyPr/{{{_A}}}normAutofit")
    assert autofit is not None
    assert autofit.get("fontScale") is None


def test_apply_autofit_replaces_stale_autofit_children():
    """A bodyPr that already carries an old normAutofit (e.g. from a
    previous polish run) has it removed before the new one is
    added, so autofit elements never accumulate."""
    sp = ET.fromstring(
        f'<p:sp xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:txBody><a:bodyPr>"
        '<a:normAutofit fontScale="70000"/>'
        "</a:bodyPr><a:p/></p:txBody></p:sp>"
    )

    _apply_autofit(sp, 1.0)

    tx_body = sp.find(f"{{{_P}}}txBody")
    body_pr = tx_body.find(f"{{{_A}}}bodyPr")
    autofits = body_pr.findall(f"{{{_A}}}normAutofit")
    assert len(autofits) == 1
    assert autofits[0].get("fontScale") is None


def test_polish_pptx_falls_back_to_master_frames_without_layout(tmp_path):
    """A slide whose _slide_layout lookup fails (no _rels part at
    all) still gets processed using the master's own frame geometry,
    instead of crashing or silently skipping the slide."""
    master = (
        f'<p:sldMaster xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="1"/>'
        "</p:nvPr></p:nvSpPr>"
        '<p:spPr><a:xfrm><a:ext cx="6000000" cy="300000"/>'
        "</a:xfrm></p:spPr></p:sp></p:sldMaster>"
    )
    slide = (
        f'<p:sld xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="1"/>'
        "</p:nvPr></p:nvSpPr>"
        "<p:spPr/><p:txBody><a:bodyPr/>"
        + _dense_paragraph_xml(6)
        + "</p:txBody></p:sp></p:sld>"
    )
    pptx = tmp_path / "no_layout.pptx"
    with zipfile.ZipFile(pptx, "w") as z:
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slides/slide1.xml", slide)
        # deliberately no ppt/slides/_rels/slide1.xml.rels

    polish_pptx(pptx)

    with zipfile.ZipFile(pptx) as z:
        out_xml = z.read("ppt/slides/slide1.xml").decode()
    fit = re.search(r"<a:normAutofit[^>]*/>", out_xml)
    assert fit is not None
    assert 'fontScale="40000"' in fit.group(0)
    assert 'lnSpcReduction="10000"' in fit.group(0)


def test_polish_pptx_content_placeholder_falls_back_to_body_one(tmp_path):
    """One slide, three shapes: a chrome placeholder (sldNum) is
    skipped untouched; a placeholder with no <p:txBody> is skipped
    without crashing; and a content placeholder whose own idx has no
    frame falls back to the master's body/1 frame and still gets
    autofit applied."""
    master = (
        f'<p:sldMaster xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="1"/>'
        "</p:nvPr></p:nvSpPr>"
        '<p:spPr><a:xfrm><a:ext cx="6000000" cy="300000"/>'
        "</a:xfrm></p:spPr></p:sp></p:sldMaster>"
    )
    slide = (
        f'<p:sld xmlns:p="{_P}" xmlns:a="{_A}">'
        # 1: chrome placeholder, must be skipped untouched.
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="sldNum" idx="10"/>'
        "</p:nvPr></p:nvSpPr><p:spPr/>"
        "<p:txBody><a:bodyPr/>"
        "<a:p><a:r><a:t>1</a:t></a:r></a:p>"
        "</p:txBody></p:sp>"
        # 2: placeholder with no txBody at all.
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="2"/>'
        "</p:nvPr></p:nvSpPr><p:spPr/></p:sp>"
        # 3: content placeholder, own idx unknown, falls back to
        # the master's body/1 frame.
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="5"/>'
        "</p:nvPr></p:nvSpPr><p:spPr/>"
        "<p:txBody><a:bodyPr/>"
        + _dense_paragraph_xml(6)
        + "</p:txBody></p:sp></p:sld>"
    )
    pptx = tmp_path / "fallback.pptx"
    with zipfile.ZipFile(pptx, "w") as z:
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slides/slide1.xml", slide)

    polish_pptx(pptx)

    with zipfile.ZipFile(pptx) as z:
        out_xml = z.read("ppt/slides/slide1.xml").decode()

    # Only shape 3 gets autofit; shapes 1 and 2 are untouched.
    assert out_xml.count("<a:normAutofit") == 1
    sldnum_block = out_xml.split('idx="10"')[1].split("</p:sp>")[0]
    assert "normAutofit" not in sldnum_block
    assert out_xml.count("<p:txBody>") == 2

    fit = re.search(r"<a:normAutofit[^>]*/>", out_xml)
    assert fit is not None
    assert 'fontScale="40000"' in fit.group(0)


def test_polish_pptx_skips_shape_when_no_frame_available_at_all(tmp_path):
    """A content placeholder whose own idx has no frame, and whose
    master has NO body/1 fallback either, is skipped entirely; since
    it is the only shape on the only slide, nothing in the deck
    changes and polish_pptx must leave the pptx file byte-for-byte
    untouched (the early return when no replacements were made)."""
    master = f'<p:sldMaster xmlns:p="{_P}" xmlns:a="{_A}"/>'
    slide = (
        f'<p:sld xmlns:p="{_P}" xmlns:a="{_A}">'
        "<p:sp><p:nvSpPr><p:nvPr>"
        '<p:ph type="body" idx="7"/>'
        "</p:nvPr></p:nvSpPr><p:spPr/>"
        "<p:txBody><a:bodyPr/>"
        "<a:p><a:r><a:t>orphan</a:t></a:r></a:p>"
        "</p:txBody></p:sp></p:sld>"
    )
    pptx = tmp_path / "no_frame.pptx"
    with zipfile.ZipFile(pptx, "w") as z:
        z.writestr("ppt/slideMasters/slideMaster1.xml", master)
        z.writestr("ppt/slides/slide1.xml", slide)
    original_bytes = pptx.read_bytes()

    polish_pptx(pptx)  # must not raise

    assert pptx.read_bytes() == original_bytes
