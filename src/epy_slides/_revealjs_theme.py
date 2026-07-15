"""Derive reveal.js theme CSS from an epy_slides :class:`Theme`.

reveal.js exposes its look through a set of ``--r-*`` CSS custom
properties plus a handful of element rules. Rather than hand-author a
separate reveal theme for each of the nine epyson layouts, we map a
Theme's ``css_vars`` (the same palette/typography that drives the
document chrome) onto reveal's variables at runtime, so the bundled
identities stay the single source of truth.

Slide *sizing* is intentionally NOT taken from the document theme — its
point sizes suit an A4 page, not a projected slide — so reveal's own
proportional scale is kept and only colours, fonts and weights are
themed.
"""

from __future__ import annotations

from epy_slides._design import design_css
from epy_slides.themes_base import Theme

CALLOUT_KINDS = ("note", "tip", "warning", "important", "caution")


def _v(theme: Theme, key: str, default: str = "") -> str:
    """Return a css var from *theme*, falling back to *default*."""
    return theme.css_vars.get(key, default)


def reveal_css_for(theme: Theme) -> str:
    """Return a CSS block that themes a reveal.js deck from *theme*.

    The result is raw CSS (no surrounding ``<style>``) meant to be placed
    in the document head *after* reveal's base stylesheet so it overrides
    the bundled base theme.
    """
    bg = _v(theme, "bg", "#ffffff")
    fg = _v(theme, "fg", "#222222")
    heading = _v(theme, "heading-color", fg)
    link = _v(theme, "link", "#2a76dd")
    link_hover = _v(theme, "link-hover", link)
    code_bg = _v(theme, "code-bg", "#f0f0f0")
    code_fg = _v(theme, "code-fg", fg)
    border = _v(theme, "border", "#cccccc")
    font_text = _v(theme, "font-family-text", "Helvetica, Arial, sans-serif")
    font_head = _v(theme, "font-family-headings", font_text)
    font_code = _v(theme, "font-family-code", "monospace")
    h_weight = _v(theme, "h2-weight", "700")
    quote_rule = _v(theme, "quote-rule", link)
    bg_quote = _v(theme, "bg-quote", code_bg)
    table_hbg = _v(theme, "table-header-bg", code_bg)
    table_htext = _v(theme, "table-header-text", fg)
    mark_bg = _v(theme, "mark-bg", "#fcf8a0")

    callouts = "\n".join(
        f".reveal .callout-{k} {{ "
        f"background:{_v(theme, f'callout-{k}-bg', code_bg)}; "
        f"border-left:4px solid {_v(theme, f'callout-{k}-border', border)}; "
        f"padding:0.4em 0.7em; border-radius:4px; margin:0.4em 0; }}"
        for k in CALLOUT_KINDS
    )

    return f""":root {{
  --r-background-color: {bg};
  --r-main-font: {font_text};
  --r-main-color: {fg};
  /* A 960x540 slide is shorter than reveal's default canvas, so its 42px
     base font overflows content-rich slides off the page in the PDF.
     A smaller base plus tighter heading/paragraph spacing (below) keeps a
     heading + paragraph + equation + callout slide within one slide. */
  --r-main-font-size: 32px;
  --r-heading1-size: 2.0em;
  --r-heading2-size: 1.5em;
  --r-heading3-size: 1.2em;
  --r-block-margin: 16px;
  --r-heading-font: {font_head};
  --r-heading-color: {heading};
  --r-heading-font-weight: {h_weight};
  --r-link-color: {link};
  --r-link-color-hover: {link_hover};
  --r-code-font: {font_code};
  --r-selection-background-color: {mark_bg};
  --r-selection-color: {fg};
  --epy-primary: {link};
  --epy-fg: {fg};
  --epy-bg: {bg};
  --epy-soft: {_v(theme, "bg-soft", code_bg)};
  --epy-border: {border};
}}
/* Tighten vertical rhythm so dense slides fit the page in the PDF. */
.reveal h1, .reveal h2 {{ margin: 0 0 0.4em; }}
.reveal h3, .reveal h4 {{ margin: 0 0 0.3em; }}
.reveal p {{ margin: 0.4em 0; }}
.reveal .callout-note, .reveal .callout-tip, .reveal .callout-warning,
.reveal .callout-important, .reveal .callout-caution {{
  padding: 0.4em 0.7em; margin: 0.45em 0;
}}
.reveal mjx-container[display="true"] {{ margin: 0.5em 0; }}
.reveal-viewport {{ background: {bg}; }}
.reveal {{ font-family: {font_text}; color: {fg}; }}
.reveal h1, .reveal h2, .reveal h3,
.reveal h4, .reveal h5, .reveal h6 {{
  font-family: {font_head}; color: {heading};
  font-weight: {h_weight}; text-transform: none;
}}
.reveal a {{ color: {link}; }}
.reveal a:hover {{ color: {link_hover}; }}
.reveal pre {{ width: 100%; box-shadow: none; font-size: 0.55em; }}
.reveal pre code {{
  background: {code_bg}; color: {code_fg};
  border: 1px solid {border}; border-radius: 4px;
  padding: 0.6em 0.8em; max-height: none;
}}
.reveal code {{ font-family: {font_code}; }}
.reveal blockquote {{
  background: {bg_quote}; border-left: 5px solid {quote_rule};
  box-shadow: none; width: auto; padding: 0.4em 0.8em; font-style: normal;
}}
.reveal table th {{ background: {table_hbg}; color: {table_htext}; }}
.reveal table td, .reveal table th {{ border-color: {border}; }}
.reveal mark {{ background: {mark_bg}; color: {fg}; }}
.reveal section img {{
  border: none; box-shadow: none; background: transparent;
}}
/* Keep any image within the slide so nothing spills past the page edge in
   the PDF: cap the height and let object-fit preserve the aspect ratio even
   when an explicit width would otherwise make the image too tall. */
.reveal .slides section img {{
  max-width: 100%; max-height: 62vh; object-fit: contain;
}}
.reveal .slides section .slide-image-left img,
.reveal .slides section .slide-image-right img {{ max-height: 70vh; }}
/* A full-bleed background image must cover, not overflow. */
.reveal .slides section.slide-image-fullbleed img {{
  max-height: 100vh; width: 100%; object-fit: cover;
}}
.reveal .columns {{
  display: flex; flex-direction: row; gap: 1.2em; align-items: flex-start;
}}
.reveal .column {{ flex: 1 1 0; min-width: 0; }}
.reveal .slide-footer {{
  position: absolute; bottom: 0.5em; left: 0; width: 100%;
  text-align: center; font-size: 0.4em; color: {fg}; opacity: 0.6;
}}
.reveal .slide-logo {{
  position: fixed; bottom: 0.5em; right: 0.7em;
  max-height: 8%; opacity: 0.9; z-index: 10;
}}
{callouts}
.reveal .slide-image-left .columns {{
  display: grid; grid-template-columns: 42% 1fr; align-items: center;
}}
.reveal .slide-image-right .columns {{
  display: grid; grid-template-columns: 1fr 42%; align-items: center;
}}
.reveal .slide-quote-portrait .columns {{
  display: grid; grid-template-columns: 30% 1fr; align-items: center;
}}
.reveal .slide-image-left img, .reveal .slide-image-right img,
.reveal .slide-quote-portrait img {{ width: 100%; border-radius: 8px; }}
.reveal .mermaid, .reveal .nomnoml {{ text-align: center; margin: 0.4em 0; }}
.reveal .mermaid svg, .reveal .nomnoml svg {{
  display: inline-block; max-height: 62vh;
}}
/* Centering is done here, not by reveal's JS (which misplaces slides in the
   PDF). Every slide fills its height; ``center`` layouts pack their content
   to the middle, content layouts stay top-aligned. */
.reveal .slides > section {{
  height: 100%; box-sizing: border-box;
  /* Inset the content from the slide edges so paragraphs and headings don't
     run to the very border on screen / in the HTML export (matches the PDF's
     print margin). Padding percentages resolve against the deck width, so the
     vertical inset stays modest to avoid overflowing dense slides. */
  padding: 2.2% 6%;
  display: flex; flex-direction: column; justify-content: flex-start;
}}
/* Full-bleed image slides must reach the edge — no inset. */
.reveal .slides > section.slide-image-fullbleed {{ padding: 0; }}
.reveal .slides > section.center {{ justify-content: center; }}
.reveal .slides > section.slide-title {{ justify-content: center; }}
.reveal .slides > section.slide-section {{
  justify-content: center; align-items: center; text-align: center;
}}
.reveal .slides > section.slide-quote {{ justify-content: center; }}
.reveal .slides > section.slide-image-fullbleed {{
  justify-content: center; align-items: center;
}}
/* A title over a full-bleed image needs a legible plate so it reads on any
   photo and in any theme (dark text on a busy image would vanish). */
.reveal .slides section.slide-image-fullbleed h1,
.reveal .slides section.slide-image-fullbleed h2 {{
  color: #ffffff;
  background: rgba(0, 0, 0, 0.5);
  padding: 0.2em 0.6em; border: none; border-radius: 10px;
  box-shadow: 0 2px 14px rgba(0, 0, 0, 0.45);
  text-shadow: 0 2px 6px rgba(0, 0, 0, 0.7);
  -webkit-box-decoration-break: clone; box-decoration-break: clone;
}}
""" + design_css(theme, scope=".reveal ")
