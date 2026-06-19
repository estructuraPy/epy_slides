"""Render slide-structured Markdown to reveal.js (HTML) and PPTX via Pandoc.

A single source format feeds every output:

* :func:`render_revealjs` — Markdown → reveal.js sections (Pandoc) wrapped
  in a self-contained deck (:mod:`epy_slides.template`). Used for the live
  preview, the standalone HTML export and the print-to-PDF source.
* :func:`export_pptx` — Markdown → PowerPoint (Pandoc's ``pptx`` writer)
  with a per-theme reference document.

The conversion is delegated to Pandoc (bundled by ``pypandoc-binary``);
:mod:`epy_slides.slide_md` adapts the shared source for each writer.
"""

from __future__ import annotations

import shutil
import tempfile
from importlib import resources
from pathlib import Path

import pypandoc

from epy_slides._media_export import (
    collect_diagrams,
    render_diagram_pngs,
    substitute_diagram_images,
)
from epy_slides.slide_md import (
    diagram_engines,
    expand_for_pptx,
    expand_for_revealjs,
)
from epy_slides.snippets import parse_front_matter
from epy_slides.template import build_reveal_document

# Pandoc input dialect: CommonMark-ish Markdown plus the Quarto-style
# extensions the editor relies on (fenced divs for columns/notes/callouts,
# dollar math, pipe/grid tables, fenced-code attributes, task lists…).
PANDOC_FORMAT = (
    "markdown"
    "+fenced_divs"
    "+bracketed_spans"
    "+fenced_code_attributes"
    "+link_attributes"
    "+inline_code_attributes"
    "+tex_math_dollars"
    "+tex_math_single_backslash"
    "+yaml_metadata_block"
    "+pipe_tables"
    "+grid_tables"
    "+raw_html"
    "+raw_attribute"
    "+implicit_figures"
    "+task_lists"
    "+fancy_lists"
    "+startnum"
    "+smart"
    "+strikeout"
    "+subscript"
    "+superscript"
)


def render_revealjs(
    source: str,
    base_dir: Path | None = None,
    *,
    title: str = "epy_slides",
    theme_css: str = "",
    for_export: bool = False,
    continuous: bool = False,
) -> str:
    """Render slide Markdown ``source`` to a self-contained reveal.js deck.

    Args:
        source: Slide-structured Markdown (YAML front matter + ``##``
            slides). Layout directives and fenced divs are honoured.
        base_dir: Directory used as the HTML ``<base>`` so relative image
            paths resolve.
        title: Fallback ``<title>``; overridden by ``title:`` front matter.
        theme_css: Reveal theme CSS for the active visual theme.
        for_export: Tweaks the deck for export (no on-screen chrome).
        continuous: Render the deck in reveal's scroll view — one
            continuous scrollable page instead of discrete slides. Used
            for the HTML export.

    Returns:
        A complete, self-contained HTML5 reveal.js document.
    """
    metadata = parse_front_matter(source)
    if metadata.get("title"):
        title = metadata["title"]
    prepared = expand_for_revealjs(source)
    body = pypandoc.convert_text(
        prepared,
        to="revealjs",
        format=PANDOC_FORMAT,
        extra_args=[
            "--slide-level=2",
            "--highlight-style=tango",
            "--wrap=preserve",
        ],
    )
    return build_reveal_document(
        body=body,
        base_dir=base_dir,
        title=title,
        metadata=metadata,
        theme_css=theme_css,
        for_export=for_export,
        continuous=continuous,
        diagrams=frozenset(diagram_engines(source)),
    )


def _resolve_reference_pptx(theme_id: str) -> Path | None:
    """Resolve a theme id to its bundled ``reference_pptx/<id>.pptx``."""
    try:
        anchor = resources.files("epy_slides.assets.reference_pptx").joinpath(
            f"{theme_id}.pptx"
        )
        with resources.as_file(anchor) as path:
            if Path(path).is_file():
                return Path(path)
    except (FileNotFoundError, ModuleNotFoundError):
        return None
    return None


def export_pptx(
    source: str,
    target: Path,
    base_dir: Path | None = None,
    *,
    theme_id: str | None = None,
) -> None:
    """Convert slide Markdown ``source`` to a ``.pptx`` file.

    The shared source is adapted by :func:`expand_for_pptx` (reveal-only
    constructs stripped, callouts rewritten to blockquotes). When a
    per-theme ``reference_pptx/<theme>.pptx`` is bundled it supplies the
    master slide layouts, fonts and colours; otherwise Pandoc's default
    template is used.

    Args:
        source: Slide-structured Markdown.
        target: Destination ``.pptx`` path (written by Pandoc).
        base_dir: Directory used to resolve relative image paths.
        theme_id: Visual theme id; defaults to the ``theme:`` front-matter
            value, then ``corporate``.
    """
    metadata = parse_front_matter(source)
    resolved_theme = theme_id or metadata.get("theme") or "corporate"

    # PowerPoint cannot draw Mermaid/nomnoml, so render each diagram to a
    # themed PNG (best-effort; falls back to the source text when no Qt is
    # available) and swap the fences for image links before the conversion.
    prepared_source = source
    diag_tmp: Path | None = None
    diagrams = collect_diagrams(source)
    if diagrams:
        from epy_slides import themes as _themes  # noqa: PLC0415
        from epy_slides._revealjs_theme import (  # noqa: PLC0415
            reveal_css_for,
        )

        diag_tmp = Path(tempfile.mkdtemp(prefix="epy_slides_pptx_diag_"))
        css = reveal_css_for(_themes.get(resolved_theme))
        pngs = render_diagram_pngs(diagrams, diag_tmp, theme_css=css)
        prepared_source = substitute_diagram_images(source, pngs)

    prepared = expand_for_pptx(prepared_source)
    extra_args = ["--slide-level=2"]
    if base_dir is not None:
        extra_args.append(f"--resource-path={base_dir}")
    reference = _resolve_reference_pptx(resolved_theme)
    if reference is not None:
        extra_args.append(f"--reference-doc={reference}")
    if (metadata.get("incremental") or "").strip().lower() in {
        "true",
        "yes",
        "1",
        "on",
    }:
        extra_args.append("--incremental")
    try:
        pypandoc.convert_text(
            prepared,
            to="pptx",
            format=PANDOC_FORMAT,
            outputfile=str(target),
            extra_args=extra_args,
        )
    finally:
        if diag_tmp is not None:
            shutil.rmtree(diag_tmp, ignore_errors=True)
