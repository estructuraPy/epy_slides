"""HTML shell builders for the reveal.js preview and exports.

Pandoc converts the slide Markdown into bare ``<section>`` elements
(``-t revealjs`` *without* ``--standalone``); this module wraps them in a
self-contained reveal.js deck whose CSS, the reveal engine and the
MathJax bundle are all inlined, so the preview, the PDF export and the
standalone HTML export render identically and offline. We control the
reveal version and initialisation rather than relying on Pandoc's
template, which targets older reveal releases.
"""

from __future__ import annotations

import html
import json
from functools import lru_cache
from importlib import resources
from pathlib import Path

_REVEAL_PKG = "epy_slides.assets.revealjs"

# Aspect ratio → reveal presentation size (px). reveal scales the deck to
# fit the viewport; these only fix the design proportions and the PDF page.
ASPECT_SIZES: dict[str, tuple[int, int]] = {
    "16:9": (960, 540),
    "4:3": (960, 720),
}
DEFAULT_ASPECT = "16:9"

_TRUTHY_VALUES = {"true", "yes", "1", "on"}


def is_truthy(value: str | None) -> bool:
    """Interpret a YAML-ish scalar string as a boolean."""
    if value is None:
        return False
    return value.strip().lower() in _TRUTHY_VALUES


_MATHJAX_CONFIG = """
<script>
window.MathJax = {
  tex: {
    inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
    displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
    processEscapes: true,
    tags: 'none'
  },
  svg: { fontCache: 'global' },
  startup: {
    ready() {
      MathJax.startup.defaultReady();
      MathJax.startup.promise.then(() => {
        window._mathjax_done = true;
      });
    }
  }
};
</script>
"""


@lru_cache(maxsize=1)
def _load_mathjax_script() -> str:
    """Return the inline MathJax v3 bundle (tex-svg-full, ~2 MB), cached."""
    js = (
        resources.files("epy_slides.assets")
        .joinpath("mathjax")
        .joinpath("tex-svg-full.js")
        .read_text(encoding="utf-8")
    )
    return f"<script>{js}</script>"


@lru_cache(maxsize=16)
def _reveal_text(*parts: str) -> str:
    """Read a bundled reveal.js asset (cached) as text."""
    node = resources.files(_REVEAL_PKG)
    for part in parts:
        node = node.joinpath(part)
    return node.read_text(encoding="utf-8")


def _base_href(base_dir: Path | None) -> str:
    """Build a ``<base>`` tag so relative images and links resolve."""
    if base_dir is None:
        return ""
    uri = base_dir.resolve().as_uri()
    if not uri.endswith("/"):
        uri += "/"
    return f'<base href="{uri}">'


def normalize_aspect(value: str | None) -> str:
    """Return a valid aspect-ratio key, defaulting to 16:9."""
    key = (value or "").strip()
    return key if key in ASPECT_SIZES else DEFAULT_ASPECT


def slide_dimensions(metadata: dict[str, str]) -> tuple[int, int]:
    """Return the ``(width, height)`` for a deck's aspect ratio."""
    return ASPECT_SIZES[normalize_aspect(metadata.get("aspect-ratio"))]


def _title_slide(metadata: dict[str, str]) -> str:
    """Build a reveal title ``<section>`` from front matter, if any."""
    title = metadata.get("title")
    subtitle = metadata.get("subtitle")
    author = metadata.get("author")
    date = metadata.get("date")
    if not (title or subtitle or author or date):
        return ""
    parts = ['<section class="title-slide slide-title center">']
    if title:
        parts.append(f'<h1 class="deck-title">{html.escape(title)}</h1>')
    if subtitle:
        parts.append(
            f'<h3 class="deck-subtitle">{html.escape(subtitle)}</h3>'
        )
    if author:
        parts.append(f'<p class="deck-author">{html.escape(author)}</p>')
    if date:
        parts.append(f'<p class="deck-date">{html.escape(date)}</p>')
    parts.append("</section>")
    return "\n".join(parts)


def _overlays(metadata: dict[str, str]) -> str:
    """Build the fixed footer / logo overlays from front matter."""
    out: list[str] = []
    footer = metadata.get("footer")
    if footer:
        out.append(
            f'<div class="slide-footer">{html.escape(footer)}</div>'
        )
    logo = metadata.get("logo")
    if logo:
        out.append(
            f'<img class="slide-logo" src="{html.escape(logo, quote=True)}"'
            ' alt="">'
        )
    return "\n".join(out)


def _watermark_css(metadata: dict[str, str]) -> str:
    """Return CSS painting a faint grayscale watermark behind every slide.

    Restricted to screen media so it shows live in the preview and the HTML
    export; the PDF export stamps its own watermark via ``_pdf_footer`` so
    it prints reliably on every page.
    """
    watermark = (metadata.get("watermark") or "").strip()
    if not watermark:
        return ""
    src = html.escape(watermark, quote=True)
    return (
        "@media screen {\n"
        ".reveal .slides section::after {\n"
        '  content: ""; position: absolute; inset: 0;\n'
        f'  background: url("{src}") center / 55% no-repeat;\n'
        "  opacity: 0.10; filter: grayscale(1);\n"
        "  pointer-events: none; z-index: -1;\n"
        "}\n}\n"
    )


def reveal_config(
    metadata: dict[str, str],
    *,
    width: int,
    height: int,
    for_export: bool,
    continuous: bool = False,
) -> dict[str, object]:
    """Build the ``Reveal.initialize`` config object for a deck.

    When ``continuous`` is set the deck renders in reveal's scroll view —
    every slide flows top-to-bottom as one scrollable page instead of
    discrete, separately navigated slides. Used for the HTML export so a
    shared deck reads like a continuous web page.
    """
    transition = (metadata.get("transition") or "slide").strip().lower()
    valid = {"none", "fade", "slide", "convex", "concave", "zoom"}
    if transition not in valid:
        transition = "slide"
    slide_number = is_truthy(metadata.get("slide-number"))
    config: dict[str, object] = {
        "width": width,
        "height": height,
        "margin": 0.04,
        "minScale": 0.2,
        "maxScale": 2.0,
        "center": True,
        "hash": False,
        "controls": not for_export,
        "progress": not for_export,
        "transition": transition,
        "slideNumber": "c/t" if slide_number else False,
        "pdfMaxPagesPerSlide": 1,
        "pdfSeparateFragments": False,
    }
    if continuous:
        config["view"] = "scroll"
        config["scrollSnap"] = False
        config["controls"] = False
        config["progress"] = False
    return config


def build_reveal_document(
    body: str,
    base_dir: Path | None,
    title: str,
    metadata: dict[str, str] | None = None,
    theme_css: str = "",
    *,
    for_export: bool = False,
    continuous: bool = False,
) -> str:
    """Assemble a self-contained reveal.js deck around Pandoc's sections.

    Args:
        body: The ``<section>`` markup produced by Pandoc's revealjs
            writer (without ``--standalone``).
        base_dir: Directory used as the HTML ``<base>`` so relative image
            paths resolve in the preview and exports.
        title: Document ``<title>``.
        metadata: YAML front matter (title slide, aspect ratio,
            transition, footer, logo, slide number).
        theme_css: Reveal theme CSS derived from the active visual theme
            (see :func:`epy_slides._revealjs_theme.reveal_css_for`).
        for_export: Tweaks the reveal config for a clean export (no
            controls/progress chrome).
        continuous: Render the deck in reveal's scroll view — one
            continuous scrollable page instead of discrete slides. Used
            by the HTML export.

    Returns:
        A complete, self-contained HTML5 reveal.js document.
    """
    meta = metadata or {}
    width, height = slide_dimensions(meta)
    config = reveal_config(
        meta, width=width, height=height,
        for_export=for_export, continuous=continuous,
    )
    reset_css = _reveal_text("dist", "reset.css")
    reveal_css = _reveal_text("dist", "reveal.css")
    base_theme = _reveal_text("dist", "theme", "white.css")
    reveal_js = _reveal_text("dist", "reveal.js")
    title_slide = _title_slide(meta)
    overlays = _overlays(meta)
    init = (
        "<script>\n"
        "document.addEventListener('DOMContentLoaded', function () {\n"
        "  var deck = new Reveal(document.querySelector('.reveal'), "
        f"{json.dumps(config)});\n"
        "  deck.initialize().then(function () { window._reveal_done = true; });\n"
        "});\n"
        "</script>\n"
    )
    return (
        "<!doctype html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="utf-8">\n'
        f"{_base_href(base_dir)}\n"
        f"<title>{html.escape(title)}</title>\n"
        "<style>\n"
        f"{reset_css}\n{reveal_css}\n{base_theme}\n"
        ".reveal aside.notes { display: none; }\n"
        f"{theme_css}\n"
        f"{_watermark_css(meta)}"
        "</style>\n"
        f"{_MATHJAX_CONFIG}\n"
        f"{_load_mathjax_script()}\n"
        "</head>\n"
        "<body>\n"
        '<div class="reveal">\n'
        '<div class="slides">\n'
        f"{title_slide}\n{body}\n"
        "</div>\n"
        f"{overlays}\n"
        "</div>\n"
        f"<script>{reveal_js}</script>\n"
        f"{init}"
        "</body>\n"
        "</html>\n"
    )
