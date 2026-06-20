"""Renderer tests: bibliography front matter → citations in HTML."""

from __future__ import annotations

import re

from epy_slides.renderer import (
    CSL_STYLES,
    _bibliography_args,
    _ensure_refs_slide,
    _resolve_csl,
    render_revealjs,
)


def test_csl_styles_keys():
    assert "ieee" in CSL_STYLES
    assert "apa" in CSL_STYLES
    assert "chicago" in CSL_STYLES


def test_resolve_csl_ieee_returns_file():
    path = _resolve_csl("ieee", None)
    assert path is not None
    assert path.is_file()
    assert path.suffix == ".csl"


def test_resolve_csl_default_is_ieee():
    path_default = _resolve_csl(None, None)
    path_ieee = _resolve_csl("ieee", None)
    assert path_default is not None
    assert path_ieee is not None
    assert path_default == path_ieee


def test_resolve_csl_apa():
    path = _resolve_csl("apa", None)
    assert path is not None
    assert path.is_file()


def test_resolve_csl_chicago():
    path = _resolve_csl("chicago", None)
    assert path is not None
    assert path.is_file()


def test_bibliography_args_empty_when_no_bib():
    args = _bibliography_args({}, None)
    assert args == []


def test_bibliography_args_empty_when_bib_missing(tmp_path):
    args = _bibliography_args(
        {"bibliography": "nonexistent.bib"}, tmp_path
    )
    assert args == []


def test_bibliography_args_with_valid_bib(tmp_path):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@misc{a2020, title={X}, year={2020}}\n",
        encoding="utf-8",
    )
    args = _bibliography_args(
        {"bibliography": "refs.bib"}, tmp_path
    )
    assert "--citeproc" in args
    joined = " ".join(args)
    assert "refs.bib" in joined


def test_ensure_refs_slide_appends_when_missing():
    source = (
        "---\nbibliography: refs.bib\n---\n\n## Slide A\n\ntext\n"
    )
    meta = {"bibliography": "refs.bib"}
    result = _ensure_refs_slide(source, meta)
    assert "## References" in result
    assert "{#refs}" in result


def test_ensure_refs_slide_no_duplicate_when_present():
    source = (
        "---\nbibliography: refs.bib\n---\n\n"
        "## Slide A\n\ntext\n\n"
        "## References\n\n::: {#refs}\n:::\n"
    )
    meta = {"bibliography": "refs.bib"}
    result = _ensure_refs_slide(source, meta)
    assert result.count("## References") == 1


def test_ensure_refs_slide_noop_when_no_bibliography():
    source = "## Slide A\n\ntext\n"
    result = _ensure_refs_slide(source, {})
    assert result == source


def test_render_revealjs_citation_in_section(tmp_path):
    """A deck with bibliography front matter must render citations inside
    a <section> (a real reveal.js slide), not dangling after the deck.
    """
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{navarro2020,\n"
        "  author  = {Navarro, Angel},\n"
        "  title   = {Seismic assessment},\n"
        "  journal = {JOSE},\n"
        "  year    = {2020},\n"
        "}\n",
        encoding="utf-8",
    )
    source = (
        "---\n"
        "title: Test deck\n"
        "bibliography: refs.bib\n"
        "---\n\n"
        "## Introduction\n\n"
        "As shown in [@navarro2020], this works.\n"
    )
    html = render_revealjs(source, base_dir=tmp_path)
    # The citation must be resolved (not left as [@navarro2020])
    assert "[@navarro2020]" not in html
    # The references entry must be inside a <section>
    section_pattern = re.compile(
        r"<section[^>]*>.*?navarro.*?</section>",
        re.DOTALL | re.IGNORECASE,
    )
    assert section_pattern.search(html), (
        "References were not placed inside a <section> slide. "
        "Check _ensure_refs_slide."
    )
