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
import re
from functools import lru_cache
from importlib import resources
from pathlib import Path

from epy_slides.epyson import is_dark

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
        // Typesetting can change content height, so re-fit any slide whose
        // content now overflows before the export poll reads _mathjax_done.
        if (window._epyAutofit) { window._epyAutofit(); }
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


# Default watermark size (fraction of slide width) and opacity. The screen
# opacity is higher than the print stamp because the on-screen mark relies
# on a blend mode for contrast rather than a flat alpha wash.
_WATERMARK_SIZE = "32%"
_WATERMARK_OPACITY = "0.12"
_THEME_BG_RE = re.compile(r"--r-background-color:\s*([^;]+);")


def _theme_background(theme_css: str) -> str:
    """Extract the deck background colour from the compiled theme CSS."""
    match = _THEME_BG_RE.search(theme_css or "")
    return match.group(1).strip() if match else "#ffffff"


def _watermark_css(metadata: dict[str, str], theme_css: str = "") -> str:
    """Return CSS painting a faint watermark behind every slide.

    The mark adapts to the deck background luminance so it stays legible on
    light and dark themes alike, and uses ``mix-blend-mode: difference`` on
    full-bleed image slides so it never washes out over a photo. Screen
    media only: the PDF export stamps its own watermark via ``_pdf_footer``.
    """
    watermark = (metadata.get("watermark") or "").strip()
    if not watermark:
        return ""
    src = html.escape(watermark, quote=True)
    # Size (fraction of slide width) and opacity are tunable from the front
    # matter so a busy or oversized mark can be dialled back.
    size = (metadata.get("watermark-size") or _WATERMARK_SIZE).strip()
    opacity = (
        metadata.get("watermark-opacity") or _WATERMARK_OPACITY
    ).strip()
    # On a light deck ``multiply`` sinks the mark into the page; on a dark
    # deck ``screen`` + ``invert`` lifts it. Either reads as a faint ghost
    # instead of vanishing at low alpha the way flat grayscale did.
    if is_dark(_theme_background(theme_css)):
        blend, extra_filter = "screen", " filter: invert(1);"
    else:
        blend, extra_filter = "multiply", ""
    return (
        "@media screen {\n"
        ".reveal .slides section::after {\n"
        '  content: ""; position: absolute; inset: 0;\n'
        f'  background: url("{src}") center / {size} no-repeat;\n'
        f"  opacity: {opacity}; mix-blend-mode: {blend};{extra_filter}\n"
        "  pointer-events: none; z-index: -1;\n"
        "}\n"
        # Over an arbitrary full-bleed photo neither multiply nor screen is
        # guaranteed to show; ``difference`` always yields contrast.
        ".reveal .slides section.slide-image-fullbleed::after {\n"
        "  mix-blend-mode: difference; opacity: 0.16;\n"
        "}\n}\n"
    )


def watermark_pdf_params(metadata: dict[str, str]) -> tuple[float, float]:
    """Return ``(width_ratio, opacity)`` for the PDF watermark stamp.

    Reads the same ``watermark-size`` (a percentage of the page width) and
    ``watermark-opacity`` front-matter keys as the on-screen watermark, so a
    deck's watermark looks the same in the preview and the printed PDF.
    """
    raw = (metadata.get("watermark-size") or "32%").strip().rstrip("%")
    try:
        ratio = float(raw) / 100.0
    except ValueError:
        ratio = 0.32
    ratio = max(0.05, min(1.0, ratio))
    try:
        opacity = float((metadata.get("watermark-opacity") or "0.10").strip())
    except ValueError:
        opacity = 0.10
    return ratio, max(0.02, min(1.0, opacity))


# Fraction of the viewport reveal keeps clear around slide content. The
# default gives more breathing room than reveal's own 0.04.
DEFAULT_MARGIN = 0.06
_MAX_MARGIN = 0.3


def _read_margin(metadata: dict[str, str]) -> float:
    """Return the slide margin fraction from the front matter.

    Accepts a bare fraction (``0.08``) or a percentage (``8%``). Out-of-range
    or unparseable values fall back to :data:`DEFAULT_MARGIN`; the result is
    clamped to ``[0, 0.3]`` so a deck can never push its content off-canvas.
    """
    raw = (metadata.get("margin") or "").strip()
    if not raw:
        return DEFAULT_MARGIN
    try:
        value = float(raw[:-1]) / 100.0 if raw.endswith("%") else float(raw)
    except ValueError:
        return DEFAULT_MARGIN
    return max(0.0, min(_MAX_MARGIN, value))


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
        "margin": _read_margin(metadata),
        "minScale": 0.2,
        "maxScale": 2.0,
        # reveal's JS vertical centering computes per-slide ``top`` offsets
        # that misplace slides across page boundaries in the print-pdf
        # export (slides overlap / bleed onto the wrong page). Centering is
        # done with CSS flexbox instead (see ``reveal_css_for``).
        "center": False,
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


_DIAGRAM_PKG = {
    "mermaid": [("epy_slides.assets.mermaid", "mermaid.min.js")],
    # nomnoml needs its layout dependency (graphre) loaded first.
    "nomnoml": [
        ("epy_slides.assets.nomnoml", "graphre.js"),
        ("epy_slides.assets.nomnoml", "nomnoml.js"),
    ],
}


@lru_cache(maxsize=4)
def _load_diagram_script(engine: str) -> str:
    """Return the bundled engine file(s) wrapped in ``<script>`` (cached)."""
    parts: list[str] = []
    for pkg, name in _DIAGRAM_PKG[engine]:
        js = resources.files(pkg).joinpath(name).read_text(encoding="utf-8")
        parts.append(f"<script>{js}</script>")
    return "".join(parts)


_MERMAID_CONFIG = """
<script>
window._epy_init_mermaid = function () {
  if (!window.mermaid) return Promise.resolve();
  var cs = getComputedStyle(document.documentElement);
  function v(n, d) { return (cs.getPropertyValue(n) || d).trim(); }
  mermaid.initialize({
    startOnLoad: false, securityLevel: 'loose', theme: 'base',
    themeVariables: {
      background: v('--epy-bg', '#ffffff'),
      primaryColor: v('--epy-soft', '#eeeeee'),
      primaryTextColor: v('--epy-fg', '#222222'),
      primaryBorderColor: v('--epy-primary', '#2a76dd'),
      lineColor: v('--epy-primary', '#2a76dd'),
      secondaryColor: v('--epy-bg', '#ffffff'),
      tertiaryColor: v('--epy-bg', '#ffffff'),
      fontFamily: v('--r-main-font', 'sans-serif')
    }
  });
  // reveal hides every slide but the active one, so mermaid.run() (which
  // measures the element in place) would size a hidden diagram to zero.
  // mermaid.render() measures in its own temporary container on <body>
  // instead, so it renders at full size regardless of slide visibility.
  var els = Array.prototype.slice.call(
    document.querySelectorAll('pre.mermaid, .mermaid')
  );
  return Promise.all(els.map(function (el, i) {
    var src = el.textContent;
    return mermaid.render('epy-mermaid-' + i, src).then(function (out) {
      var div = document.createElement('div');
      div.className = 'mermaid';
      div.innerHTML = out.svg;
      var svg = div.querySelector('svg');
      if (svg) {
        // mermaid emits width="100%" + max-width:<natural>; inside a
        // shrink-to-fit centred slide "100%" collapses to ~0. Pin the SVG
        // to its natural size (from the viewBox) and let it scale down.
        var vb = (svg.getAttribute('viewBox') || '').split(/\\s+/);
        var w = parseFloat(vb[2]) || 0, h = parseFloat(vb[3]) || 0;
        svg.removeAttribute('width');
        svg.removeAttribute('height');
        svg.style.maxWidth = '100%';
        svg.style.height = 'auto';
        if (w) { svg.style.width = w + 'px'; }
        if (w && h) { svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h); }
      }
      el.replaceWith(div);
    }).catch(function (e) {
      el.textContent = 'mermaid: ' + ((e && e.message) || e);
    });
  }));
};
</script>
"""

_NOMNOML_CONFIG = """
<script>
window._epy_init_nomnoml = function () {
  if (!window.nomnoml) return Promise.resolve();
  var cs = getComputedStyle(document.documentElement);
  function v(n, d) { return (cs.getPropertyValue(n) || d).trim(); }
  var head = '#stroke: ' + v('--epy-primary', '#2a76dd') + '\\n' +
             '#fill: ' + v('--epy-soft', '#eeeeee') + '\\n';
  document.querySelectorAll('pre.nomnoml').forEach(function (el) {
    try {
      var wrap = document.createElement('div');
      wrap.className = 'nomnoml';
      wrap.innerHTML = nomnoml.renderSvg(head + el.textContent);
      el.replaceWith(wrap);
    } catch (e) { el.textContent = 'nomnoml: ' + e.message; }
  });
  return Promise.resolve();
};
</script>
"""


def _diagram_assets(diagrams: frozenset[str]) -> tuple[str, list[str]]:
    """Return ``(head_html, init_calls)`` for the diagram engines in use."""
    head = ""
    inits: list[str] = []
    if "mermaid" in diagrams:
        head += _load_diagram_script("mermaid") + _MERMAID_CONFIG
        inits.append("window._epy_init_mermaid()")
    if "nomnoml" in diagrams:
        head += _load_diagram_script("nomnoml") + _NOMNOML_CONFIG
        inits.append("window._epy_init_nomnoml()")
    return head, inits


# Restores the slide the preview was showing before a re-render. The live
# preview reloads the whole deck on every edit, which would otherwise reset
# reveal to slide 0; the editor appends ``#epypos=v:<h>.<v>`` to the preview
# URL and this hook navigates there once reveal is ready. Export URLs carry
# no such hash, so it is a no-op there.
_RESTORE_FN = (
    "window._epyRestore = function () {\n"
    "  try {\n"
    "    var m = (location.hash || '').match(/epypos=([^&]+)/);\n"
    "    if (!m) return;\n"
    "    var val = decodeURIComponent(m[1]);\n"
    "    var d = window._epyDeck;\n"
    "    if (val.charAt(0) === 'v' && d && d.slide) {\n"
    "      var p = val.slice(2).split('.');\n"
    "      d.slide(parseInt(p[0], 10) || 0, parseInt(p[1], 10) || 0);\n"
    "    }\n"
    "  } catch (e) {}\n"
    "};\n"
)


# Shrink-to-fit: reveal slides are a fixed size and clip overflow (the print
# CSS pins each page with ``overflow: hidden``), so a content-dense slide is
# silently cut off at the bottom. This wraps each leaf slide's content in an
# ``.epy-fit`` box and, when that content is taller than the slide, scales it
# down to fit. It runs after reveal lays out (and again after MathJax typesets,
# which changes heights) so both the live preview and the PDF export fit.
_AUTOFIT_FN = (
    "window._epyAutofit = function () {\n"
    "  var secs = document.querySelectorAll('.reveal .slides section');\n"
    "  Array.prototype.forEach.call(secs, function (sec) {\n"
    "    if (sec.querySelector(':scope > section')) return;\n"
    "    var fit = sec.querySelector(':scope > .epy-fit');\n"
    "    if (!fit) {\n"
    "      fit = document.createElement('div');\n"
    "      fit.className = 'epy-fit';\n"
    "      while (sec.firstChild) { fit.appendChild(sec.firstChild); }\n"
    "      sec.appendChild(fit);\n"
    "    }\n"
    "    fit.style.transform = '';\n"
    "    var cs = getComputedStyle(sec);\n"
    "    var pad = (parseFloat(cs.paddingTop) || 0) + (parseFloat(cs.paddingBottom) || 0);\n"
    "    var avail = sec.clientHeight - pad;\n"
    "    var need = fit.scrollHeight;\n"
    "    if (avail > 4 && need > avail + 1) {\n"
    "      var f = Math.max(0.4, (avail / need) * 0.98);\n"
    "      fit.style.transformOrigin = 'top center';\n"
    "      fit.style.transform = 'scale(' + f + ')';\n"
    "    }\n"
    "  });\n"
    "};\n"
)


def _print_css(width: int, height: int, margin: float) -> str:
    """Pin reveal's print-pdf pages to the exact slide height, no drift.

    reveal's own print layout left a top offset and slightly over-tall pages
    (~560 px for a 540 px slide), so each printed page captured parts of two
    slides. Forcing the page boxes to exactly ``height`` px, anchored at the
    top with overflow clipped, makes every PDF page hold exactly one slide.

    Pinning the pages also dropped reveal's on-screen ``margin`` (it lives in
    the scale transform we override away), which let content run to the very
    page edge. The same ``margin`` fraction is reapplied here as padding on
    the printed section, scaled to the slide size, so the PDF keeps the
    breathing room the preview shows. Full-bleed image slides are exempt so
    their artwork still reaches the edge.
    """
    pad_x = round(width * margin)
    pad_y = round(height * margin)
    # reveal puts the ``print-pdf`` class on <html>, so the override must be
    # anchored there (``.reveal.print-pdf`` never matches). Only the
    # ``.pdf-page`` wrappers are pinned — forcing a height on the inner
    # sections inflated reveal's leftover stack and pushed a blank page in.
    return f"""\
html.print-pdf, html.print-pdf body {{ margin: 0 !important; padding: 0 !important; }}
html.print-pdf .reveal .slides {{
  left: 0 !important; top: 0 !important; transform: none !important;
}}
html.print-pdf .pdf-page {{
  height: {height}px !important; min-height: {height}px !important;
  max-height: {height}px !important; overflow: hidden !important;
  margin: 0 !important; padding: 0 !important;
  page-break-after: always !important;
}}
/* The forced always-break above is !important, so it would clobber reveal's
   own (non-!important) ``.pdf-page:last-of-type {{ page-break-after: avoid }}``
   and make the printer emit one extra blank page after the last slide. Drop
   the break on the final page so the PDF ends on the last real slide. */
html.print-pdf .pdf-page:last-of-type {{ page-break-after: avoid !important; }}
/* reveal's print stylesheet zeroes the section box with
   ``html.reveal-print .reveal .slides section {{ padding: 0 !important }}`` —
   specificity (0,3,2). To reintroduce the slide margin (reveal's on-screen
   ``margin`` lives in the scale transform we override away) we must outrank
   it, hence the longer ``.reveal .slides .pdf-page > section`` chain (0,4,2).
   Full-bleed image slides are exempt so their artwork still reaches the edge. */
html.print-pdf .reveal .slides .pdf-page > section {{
  overflow: hidden !important; top: 0 !important;
  box-sizing: border-box !important; max-height: {height}px !important;
  padding: {pad_y}px {pad_x}px !important;
}}
html.print-pdf .reveal .slides .pdf-page > section.slide-image-fullbleed {{
  padding: 0 !important;
}}
/* Center the title / section / quote layouts on their page (reveal's JS
   centering is off, and the flex rules in reveal_css_for only match the
   preview's ``.slides > section``, not the print wrappers). The same chain
   also outranks reveal's ``display: block !important`` on print sections. */
html.print-pdf .reveal .slides .pdf-page > section.slide-title,
html.print-pdf .reveal .slides .pdf-page > section.slide-section,
html.print-pdf .reveal .slides .pdf-page > section.slide-quote,
html.print-pdf .reveal .slides .pdf-page > section.center {{
  display: flex !important; flex-direction: column;
  justify-content: center !important; align-items: center;
  box-sizing: border-box !important; padding: {pad_y}px {pad_x}px !important;
  height: {height}px !important;
}}
"""


def build_reveal_document(
    body: str,
    base_dir: Path | None,
    title: str,
    metadata: dict[str, str] | None = None,
    theme_css: str = "",
    *,
    for_export: bool = False,
    continuous: bool = False,
    diagrams: frozenset[str] = frozenset(),
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
        diagrams: Diagram engines used by the deck (``mermaid`` /
            ``nomnoml``); their bundles and init are injected when present.

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
    diagram_head, diagram_inits = _diagram_assets(diagrams)
    init = (
        "<script>\n"
        + _RESTORE_FN
        + _AUTOFIT_FN
        + "document.addEventListener('DOMContentLoaded', function () {\n"
        "  function initDeck() {\n"
        "    var deck = new Reveal(document.querySelector('.reveal'), "
        + json.dumps(config) + ");\n"
        "    window._epyDeck = deck;\n"
        "    deck.on('slidechanged', function () { window._epyAutofit(); });\n"
        "    deck.on('resize', function () { window._epyAutofit(); });\n"
        "    // reveal builds the fixed-size print pages (and pins their\n"
        "    // height) only when exporting; 'pdf-ready' is the moment those\n"
        "    // boxes exist, so this is where overflowing slides must be fit.\n"
        "    deck.on('pdf-ready', function () { window._epyAutofit(); });\n"
        "    deck.initialize().then(function () {\n"
        "      window._epyAutofit();\n"
        "      window._reveal_done = true; window._epyRestore();\n"
        "    });\n"
        "  }\n"
        "  window._diagrams_done = false;\n"
        "  Promise.all([" + ", ".join(diagram_inits) + "])"
        ".then(function () { window._diagrams_done = true; initDeck(); })\n"
        ".catch(function () { window._diagrams_done = true; initDeck(); });\n"
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
        ".reveal .slides section > .epy-fit { width: 100%; }\n"
        f"{theme_css}\n"
        f"{_print_css(width, height, _read_margin(meta))}"
        f"{_watermark_css(meta, theme_css)}"
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
        f"{diagram_head}"
        f"{init}"
        "</body>\n"
        "</html>\n"
    )
