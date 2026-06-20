"""Tests for diagram collection / substitution used by the PPTX export.

The :func:`render_diagram_pngs` rasteriser needs a running Qt WebEngine and
is exercised indirectly elsewhere; here we test the pure helpers: diagram
collection, the offscreen page HTML builder and the source substitution.
"""

from __future__ import annotations

from pathlib import Path

from epy_slides._media_export import (
    _diagram_page_html,
    collect_diagrams,
    render_diagram_pngs,
    substitute_diagram_images,
)


# ----------------------------------------------------------- collect_diagrams


def test_collect_diagrams_orders_mermaid_and_nomnoml():
    source = (
        "Intro\n"
        "```mermaid\nflowchart LR\nA-->B\n```\n"
        "Middle\n"
        "```nomnoml\n[A]->[B]\n```\n"
    )
    diagrams = collect_diagrams(source)
    assert [engine for engine, _ in diagrams] == ["mermaid", "nomnoml"]
    assert "flowchart LR" in diagrams[0][1]
    assert "[A]->[B]" in diagrams[1][1]


def test_collect_diagrams_handles_attribute_fence():
    source = "```{.mermaid}\ngraph TD\nA-->B\n```\n"
    diagrams = collect_diagrams(source)
    assert len(diagrams) == 1
    assert diagrams[0][0] == "mermaid"


def test_collect_diagrams_ignores_other_languages():
    source = "```python\nprint('hi')\n```\n"
    assert collect_diagrams(source) == []


def test_collect_diagrams_empty_source():
    assert collect_diagrams("") == []


# --------------------------------------------------------- _diagram_page_html


def test_diagram_page_html_escapes_body_and_includes_theme():
    diagrams = [("nomnoml", "[A & B]\n<x>")]
    html = _diagram_page_html(diagrams, theme_css=":root{--epy-bg:#fff;}")
    assert "&amp;" in html
    assert "&lt;x&gt;" in html
    assert "--epy-bg:#fff" in html
    assert 'class="nomnoml"' in html


def test_diagram_page_html_only_loads_used_engines():
    html = _diagram_page_html([("nomnoml", "[A]->[B]")], theme_css="")
    assert "_epy_init_nomnoml" in html
    assert "_epy_init_mermaid()" not in html


# ----------------------------------------------------- substitute_diagram_images


def test_substitute_replaces_each_fence_with_image_link():
    source = (
        "```mermaid\nA-->B\n```\n"
        "```nomnoml\n[A]->[B]\n```\n"
    )
    pngs: list[Path | None] = [Path("d0.png"), Path("d1.png")]
    out = substitute_diagram_images(source, pngs)
    assert "![](d0.png)" in out
    assert "![](d1.png)" in out
    assert "```mermaid" not in out


def test_substitute_keeps_source_when_png_is_none():
    source = "```mermaid\nA-->B\n```\n"
    out = substitute_diagram_images(source, [None])
    assert "```mermaid" in out
    assert "![]" not in out


def test_substitute_keeps_source_when_png_list_short():
    source = "```mermaid\nA-->B\n```\n"
    out = substitute_diagram_images(source, [])
    assert "```mermaid" in out


# --------------------------------------------------- render_diagram_pngs guards


def test_render_diagram_pngs_empty_returns_empty(tmp_path):
    assert render_diagram_pngs([], tmp_path) == []
