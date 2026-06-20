"""Extra renderer-branch coverage: refs-heading short circuit, reference
pptx resolution and CSL fallback to a document-relative file."""

from __future__ import annotations

from epy_slides.renderer import (
    _ensure_refs_slide,
    _resolve_csl,
    _resolve_reference_pptx,
)


def test_ensure_refs_slide_noop_when_heading_present_without_div():
    # A "## References" heading (no {#refs} div) must still suppress the
    # auto-appended slide — exercising the heading short-circuit branch.
    source = (
        "---\nbibliography: refs.bib\n---\n\n"
        "## Slide A\n\ntext\n\n"
        "## References\n\nManual list here\n"
    )
    result = _ensure_refs_slide(source, {"bibliography": "refs.bib"})
    assert result.count("## References") == 1
    assert "{#refs}" not in result


def test_resolve_reference_pptx_unknown_theme_is_none():
    assert _resolve_reference_pptx("definitely-not-a-theme") is None


def test_resolve_csl_relative_document_file(tmp_path):
    # A non-builtin csl name is resolved relative to the document dir.
    custom = tmp_path / "house.csl"
    custom.write_text("<style/>", encoding="utf-8")
    resolved = _resolve_csl("house.csl", tmp_path)
    assert resolved == custom


def test_resolve_csl_relative_missing_is_none(tmp_path):
    assert _resolve_csl("missing.csl", tmp_path) is None
