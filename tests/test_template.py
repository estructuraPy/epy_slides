"""Tests for the reveal.js HTML-shell builders in ``template.py``.

The margin / watermark-CSS paths are covered by ``test_render_revealjs``;
this file targets the aspect-ratio sizing, the title slide and overlays,
the reveal config switches, the PDF watermark params and the diagram-asset
injection in the full document builder.
"""

from __future__ import annotations

from epy_slides.template import (
    ASPECT_SIZES,
    DEFAULT_ASPECT,
    build_reveal_document,
    is_truthy,
    normalize_aspect,
    reveal_config,
    slide_dimensions,
    watermark_pdf_params,
)

# --------------------------------------------------------------- is_truthy


def test_is_truthy_recognises_true_tokens():
    for token in ("true", "Yes", "1", "ON"):
        assert is_truthy(token) is True


def test_is_truthy_false_tokens_and_none():
    assert is_truthy("false") is False
    assert is_truthy("0") is False
    assert is_truthy(None) is False
    assert is_truthy("") is False


# ------------------------------------------------------ aspect-ratio sizing


def test_normalize_aspect_valid_and_default():
    assert normalize_aspect("4:3") == "4:3"
    assert normalize_aspect("16:9") == "16:9"
    assert normalize_aspect("weird") == DEFAULT_ASPECT
    assert normalize_aspect(None) == DEFAULT_ASPECT


def test_slide_dimensions_match_aspect_sizes():
    assert slide_dimensions({"aspect-ratio": "4:3"}) == ASPECT_SIZES["4:3"]
    assert slide_dimensions({}) == ASPECT_SIZES["16:9"]


# ------------------------------------------------------ watermark_pdf_params


def test_watermark_pdf_params_defaults():
    ratio, opacity = watermark_pdf_params({})
    assert abs(ratio - 0.32) < 1e-9
    assert abs(opacity - 0.10) < 1e-9


def test_watermark_pdf_params_reads_size_and_opacity():
    ratio, opacity = watermark_pdf_params(
        {"watermark-size": "50%", "watermark-opacity": "0.25"}
    )
    assert abs(ratio - 0.50) < 1e-9
    assert abs(opacity - 0.25) < 1e-9


def test_watermark_pdf_params_clamps():
    # 200% clamps to 1.0; opacity 5 clamps to 1.0.
    ratio, opacity = watermark_pdf_params(
        {"watermark-size": "200%", "watermark-opacity": "5"}
    )
    assert ratio == 1.0
    assert opacity == 1.0


def test_watermark_pdf_params_unparseable_falls_back():
    ratio, opacity = watermark_pdf_params(
        {"watermark-size": "big", "watermark-opacity": "lots"}
    )
    assert abs(ratio - 0.32) < 1e-9
    assert abs(opacity - 0.10) < 1e-9


# --------------------------------------------------------------- reveal_config


def test_reveal_config_export_disables_chrome():
    cfg = reveal_config({}, width=960, height=540, for_export=True)
    assert cfg["controls"] is False
    assert cfg["progress"] is False


def test_reveal_config_preview_enables_chrome():
    cfg = reveal_config({}, width=960, height=540, for_export=False)
    assert cfg["controls"] is True
    assert cfg["progress"] is True


def test_reveal_config_invalid_transition_falls_back_to_slide():
    cfg = reveal_config(
        {"transition": "spin"}, width=960, height=540, for_export=False
    )
    assert cfg["transition"] == "slide"


def test_reveal_config_valid_transition_kept():
    cfg = reveal_config(
        {"transition": "fade"}, width=960, height=540, for_export=False
    )
    assert cfg["transition"] == "fade"


def test_reveal_config_slide_number():
    on = reveal_config(
        {"slide-number": "true"}, width=960, height=540, for_export=False
    )
    assert on["slideNumber"] == "c/t"
    off = reveal_config({}, width=960, height=540, for_export=False)
    assert off["slideNumber"] is False


def test_reveal_config_continuous_enables_scroll_view():
    cfg = reveal_config(
        {}, width=960, height=540, for_export=True, continuous=True
    )
    assert cfg["view"] == "scroll"
    assert cfg["scrollSnap"] is False
    assert cfg["controls"] is False


# ---------------------------------------------------- build_reveal_document


def test_build_reveal_document_basic_structure():
    html = build_reveal_document(
        "<section><h2>A</h2></section>", None, "Deck",
    )
    assert html.startswith("<!doctype html>")
    assert "<title>Deck</title>" in html
    assert '<div class="reveal">' in html
    assert "new Reveal(" in html


def test_build_reveal_document_title_slide_and_overlays():
    meta = {
        "title": "Big Deck", "subtitle": "Sub", "author": "ANM",
        "date": "2026", "footer": "Confidential", "logo": "logo.png",
    }
    html = build_reveal_document(
        "<section><h2>A</h2></section>", None, "Deck", metadata=meta,
    )
    assert "deck-title" in html
    assert "Big Deck" in html
    assert "deck-subtitle" in html
    assert "deck-author" in html
    assert "deck-date" in html
    assert 'class="slide-footer"' in html
    assert "Confidential" in html
    assert 'class="slide-logo"' in html


def test_build_reveal_document_no_title_slide_without_meta():
    html = build_reveal_document(
        "<section><h2>A</h2></section>", None, "Deck", metadata={},
    )
    assert "deck-title" not in html


def test_build_reveal_document_injects_mermaid_assets():
    html = build_reveal_document(
        "<section><pre class='mermaid'>A-->B</pre></section>",
        None, "Deck", diagrams=frozenset({"mermaid"}),
    )
    assert "_epy_init_mermaid" in html
    assert "_epy_init_nomnoml" not in html


def test_build_reveal_document_injects_nomnoml_assets():
    html = build_reveal_document(
        "<section><pre class='nomnoml'>[A]->[B]</pre></section>",
        None, "Deck", diagrams=frozenset({"nomnoml"}),
    )
    assert "_epy_init_nomnoml" in html


def test_build_reveal_document_base_href(tmp_path):
    html = build_reveal_document(
        "<section></section>", tmp_path, "Deck",
    )
    assert "<base href=" in html
