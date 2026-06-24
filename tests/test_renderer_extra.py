"""Extra renderer-branch coverage: refs-heading short circuit, reference
pptx resolution and CSL fallback to a document-relative file."""

from __future__ import annotations

from epy_slides import renderer
from epy_slides.renderer import (
    _ensure_refs_slide,
    _resolve_csl,
    _resolve_reference_pptx,
    export_pptx,
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


def test_resolve_csl_builtin_resource_missing_returns_none(monkeypatch):
    # A builtin key whose bundled .csl resource cannot be located falls
    # through to None (the resource-lookup failure branch).
    def boom(_package):
        raise FileNotFoundError("no csl assets")

    monkeypatch.setattr(renderer.resources, "files", boom)
    assert _resolve_csl("ieee", None) is None


def test_resolve_csl_builtin_resource_not_a_file_returns_none(
    tmp_path, monkeypatch
):
    # The bundled key resolves but the on-disk path is not a file: the
    # function falls through to the trailing ``return None``.
    import contextlib

    missing = tmp_path / "does_not_exist.csl"

    @contextlib.contextmanager
    def fake_as_file(_target):
        yield missing

    monkeypatch.setattr(renderer.resources, "as_file", fake_as_file)
    assert _resolve_csl("apa", None) is None


def test_resolve_reference_pptx_resource_error_returns_none(monkeypatch):
    # If the reference_pptx package cannot be resolved, return None.
    def boom(_package):
        raise ModuleNotFoundError("no reference_pptx")

    monkeypatch.setattr(renderer.resources, "files", boom)
    assert _resolve_reference_pptx("corporate") is None


def test_export_pptx_with_diagram_and_incremental(qapp, tmp_path, monkeypatch):
    # A deck with a Mermaid diagram and incremental: true drives the diagram
    # rasterisation branch (mocked to avoid Chromium), the --incremental
    # flag and the temp-dir cleanup. The diagram render is stubbed so the
    # source-text fallback is substituted in.
    rendered: dict = {}

    def fake_render(diagrams, out_dir, *, theme_css="", timeout_ms=10000):
        rendered["n"] = len(diagrams)
        return [None] * len(diagrams)

    monkeypatch.setattr(renderer, "render_diagram_pngs", fake_render)

    src = (
        "---\ntitle: Diag\nincremental: true\n---\n\n"
        "## Flow\n\n```mermaid\nflowchart LR\nA-->B\n```\n"
    )
    out = tmp_path / "diag.pptx"
    export_pptx(src, out, base_dir=tmp_path, theme_id="corporate")
    assert out.is_file()
    assert out.read_bytes()[:2] == b"PK"
    assert rendered["n"] == 1
