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

import re
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

# Citation Style Language: short names users can type in YAML
# (``citation-style: ieee``) or pick from the References menu,
# mapped to the bundled .csl file under ``epy_slides/assets/csl/``.
CSL_STYLES: dict[str, str] = {
    "ieee":      "ieee.csl",
    "apa":       "apa.csl",
    "chicago":   "chicago-author-date.csl",
    "harvard":   "harvard-cite-them-right.csl",
    "mla":       "modern-language-association.csl",
    "acs":       "american-chemical-society.csl",
    "ama":       "american-medical-association.csl",
    "vancouver": "elsevier-vancouver.csl",
    "nature":    "nature.csl",
    "science":   "science.csl",
    "asce":      "american-society-of-civil-engineers.csl",
    "elsevier":  "elsevier-harvard.csl",
    "springer":  "springer-basic-author-date.csl",
    "apsa":      "american-political-science-association.csl",
}
DEFAULT_CSL_STYLE = "ieee"

# Pandoc input dialect: CommonMark-ish Markdown plus the Quarto-style
# extensions the editor relies on (fenced divs for columns/notes/callouts,
# dollar math, pipe/grid tables, fenced-code attributes, task lists…).
# ``+citations`` enables Pandoc's citeproc ``[@key]`` syntax.
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
    "+citations"
)


# A ``::: {.card}`` div that contains a heading (``#### Title``) is emitted
# by Pandoc's revealjs writer as a nested ``<section class="card">`` rather
# than a ``<div>``. reveal then treats the slide as a vertical *stack*, which
# breaks navigation and the print-pdf page layout (a stray, mis-positioned
# page). Cards are leaf elements, so turning those sections back into divs is
# safe and keeps them as plain content.
_CARD_SECTION_RE = re.compile(
    r'<section\b[^>]*\bclass="[^"]*\bcard\b[^"]*"[^>]*>'
    r"(?P<inner>.*?)</section>",
    re.DOTALL,
)

# Detect whether the source already has an explicit references container
# (``{#refs}``) or a "## References" / "## Bibliography" slide so we do
# not double-append the placeholder.
_REFS_DIV_RE = re.compile(
    r":::\s*\{[^}]*#refs[^}]*\}",
    re.IGNORECASE,
)
_REFS_HEADING_RE = re.compile(
    r"^#{1,6}\s+(References|Bibliography)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def _cards_sections_to_divs(body: str) -> str:
    """Rewrite Pandoc's ``<section class="card">`` blocks back to divs."""
    return _CARD_SECTION_RE.sub(
        lambda m: '<div class="card">' + m.group("inner") + "</div>",
        body,
    )


def _resolve_doc_path(
    value: str, base_dir: Path | None
) -> Path | None:
    """Resolve a path declared in YAML metadata.

    ``value`` is interpreted relative to ``base_dir`` (the directory of
    the .md file) unless it is absolute. Returns ``None`` when the
    resolved path does not exist on disk.
    """
    candidate = Path(value)
    if not candidate.is_absolute() and base_dir is not None:
        candidate = (base_dir / candidate).resolve()
    return candidate if candidate.is_file() else None


def _resolve_csl(
    csl_value: str | None, base_dir: Path | None
) -> Path | None:
    """Resolve a YAML ``citation-style:`` value to a .csl file.

    Accepts a short name (``ieee`` / ``apa`` / ``chicago``) that maps to
    a bundled stylesheet, a relative path to a ``.csl`` next to the
    document, or an absolute path. ``None`` or empty selects the bundled
    default (IEEE).
    """
    key = (csl_value or DEFAULT_CSL_STYLE).strip().lower()
    if key in CSL_STYLES:
        try:
            anchor = resources.files("epy_slides.assets.csl")
            target = anchor.joinpath(CSL_STYLES[key])
            with resources.as_file(target) as path:
                if Path(path).is_file():
                    return Path(path)
        except (FileNotFoundError, ModuleNotFoundError):
            return None
        return None
    return _resolve_doc_path(csl_value or "", base_dir)


def _bibliography_args(
    metadata: dict[str, str], base_dir: Path | None
) -> list[str]:
    """Build the ``--citeproc`` / ``--bibliography`` Pandoc arguments.

    If the YAML front matter declares ``bibliography:`` and the file
    resolves on disk, citeproc is enabled. ``citation-style:`` is
    optional; it selects a bundled or custom CSL stylesheet.
    """
    bib_value = metadata.get("bibliography")
    if not bib_value:
        return []
    bib_path = _resolve_doc_path(bib_value, base_dir)
    if bib_path is None:
        return []
    extra: list[str] = [
        "--citeproc",
        f"--bibliography={bib_path}",
    ]
    csl_path = _resolve_csl(
        metadata.get("citation-style") or metadata.get("csl"),
        base_dir,
    )
    if csl_path is not None:
        extra.append(f"--csl={csl_path}")
    return extra


def _ensure_refs_slide(
    source: str, metadata: dict[str, str]
) -> str:
    """Append a References slide when bibliography is set but absent.

    Pandoc citeproc places the generated bibliography into a
    ``<div id="refs">`` container at the *end* of the converted body.
    For a reveal.js deck with ``--slide-level=2``, that container lands
    AFTER the last ``</section>`` and therefore does NOT appear as a
    slide.

    Fix: if the source declares a ``bibliography:`` but has no explicit
    ``{#refs}`` div or a ``## References`` heading, append a final
    slide that contains the ``{#refs}`` fenced div so Pandoc places the
    bibliography inside it — and reveal.js wraps it in a real
    ``<section>``.

    If the user already placed a ``{#refs}`` div or a References
    heading, this function is a no-op.
    """
    if not metadata.get("bibliography"):
        return source
    if _REFS_DIV_RE.search(source):
        return source
    if _REFS_HEADING_RE.search(source):
        return source
    return source + "\n\n## References\n\n::: {#refs}\n:::\n"


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
            When ``bibliography:`` is set in the front matter, citeproc
            is enabled and a References slide is appended automatically
            (unless the source already contains one).
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
    prepared = _ensure_refs_slide(source, metadata)
    prepared = expand_for_revealjs(prepared)
    extra_args = [
        "--slide-level=2",
        "--highlight-style=tango",
        "--wrap=preserve",
    ]
    extra_args += _bibliography_args(metadata, base_dir)
    body = pypandoc.convert_text(
        prepared,
        to="revealjs",
        format=PANDOC_FORMAT,
        extra_args=extra_args,
    )
    body = _cards_sections_to_divs(body)
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
        anchor = resources.files(
            "epy_slides.assets.reference_pptx"
        ).joinpath(f"{theme_id}.pptx")
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
    template is used. When ``bibliography:`` is set in the front matter,
    citeproc resolves citations in the PowerPoint output too.

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

        diag_tmp = Path(
            tempfile.mkdtemp(prefix="epy_slides_pptx_diag_")
        )
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
    extra_args += _bibliography_args(metadata, base_dir)
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
