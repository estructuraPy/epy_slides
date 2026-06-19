"""Slide-structured Markdown ↔ Pandoc transforms for epy_slides.

One source format feeds three exporters. Slides are separated by level-2
headings (``##``); a level-1 heading (``#``) is a section divider. Per-slide
layout is declared with an inert HTML comment directly under the heading::

    ## Market overview
    <!-- layout: two-column -->

The comment is invisible to Pandoc, so a deck still renders even if these
transforms are skipped. :func:`expand_for_revealjs` turns selected layouts
into reveal ``<section>`` classes; :func:`expand_for_pptx` strips
reveal-only constructs and rewrites callouts to blockquotes so the
PowerPoint writer produces clean slides.
"""

from __future__ import annotations

import re

LAYOUTS: tuple[str, ...] = (
    "title",
    "section",
    "title-content",
    "two-column",
    "comparison",
    "image-caption",
    "image-fullbleed",
    "quote",
    "code",
    "blank",
)

# Layouts whose slide content reads best vertically centred in reveal.
_CENTERED = {"title", "section", "quote", "blank", "image-fullbleed"}

_CALLOUT_KINDS = ("note", "tip", "warning", "important", "caution")
_CALLOUT_LABELS = {
    "note": "Note",
    "tip": "Tip",
    "warning": "Warning",
    "important": "Important",
    "caution": "Caution",
}

_LAYOUT_RE = re.compile(
    r"^[ \t]*<!--[ \t]*layout:[ \t]*(?P<name>[a-z][a-z-]*)[ \t]*-->[ \t]*$"
)
_ATX_RE = re.compile(r"^(?P<hashes>#{1,6})[ \t]+(?P<rest>.*?)[ \t]*$")
_FENCE_RE = re.compile(r"^[ \t]*(```|~~~)")
_PAUSE_RE = re.compile(r"^[ \t]*\.[ \t]+\.[ \t]+\.[ \t]*$")
_BG_ATTR_RE = re.compile(r"[ \t]*\{[^}]*background[^}]*\}")
_CALLOUT_OPEN_RE = re.compile(
    r"^:::+[ \t]*\{\.callout-(?P<kind>" + "|".join(_CALLOUT_KINDS) + r")"
    r"(?:[ \t]+(?P<attrs>[^}]*))?\}[ \t]*$"
)
_DIV_OPEN_RE = re.compile(r"^:::+[ \t]*\{")
_DIV_CLOSE_RE = re.compile(r"^:::+[ \t]*$")
_TITLE_ATTR_RE = re.compile(r'title="([^"]*)"')
_TRAILING_ATTR_RE = re.compile(r"\{(?P<inner>[^}]*)\}[ \t]*$")


def _heading_with_layout(hashes: str, rest: str, layout: str) -> str:
    """Return an ATX heading line carrying the layout's reveal classes."""
    classes = [f"slide-{layout}"]
    if layout in _CENTERED:
        classes.append("center")
    added = " ".join("." + c for c in classes)
    m = _TRAILING_ATTR_RE.search(rest)
    if m:
        inner = m.group("inner").strip()
        merged = "{" + (inner + " " if inner else "") + added + "}"
        return f"{hashes} {rest[: m.start()].rstrip()} {merged}".rstrip()
    return f"{hashes} {rest} {{{added}}}"


_MERMAID_FENCE_RE = re.compile(
    r"^[ \t]*`{3,}[ \t]*\{?\.?mermaid[^\n}]*\}?[ \t]*\n(?P<body>.*?)\n"
    r"[ \t]*`{3,}[ \t]*$",
    re.MULTILINE | re.DOTALL,
)
_NOMNOML_FENCE_RE = re.compile(
    r"^[ \t]*`{3,}[ \t]*\{?\.?nomnoml[^\n}]*\}?[ \t]*\n(?P<body>.*?)\n"
    r"[ \t]*`{3,}[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def _diagram_pre(body: str, cls: str) -> str:
    """Wrap a diagram definition in a raw-HTML ``<pre>`` of class *cls*.

    The text is HTML-escaped so characters like ``<`` (UML, DOT edges)
    survive; the browser decodes ``textContent`` before the diagram engine
    reads it.
    """
    esc = (
        body.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    )
    return f'\n```{{=html}}\n<pre class="{cls}">\n{esc}\n</pre>\n```\n'


def expand_diagrams(source: str) -> str:
    """Convert ```mermaid / ```dot fences to raw-HTML diagram placeholders.

    The browser-side engines (Mermaid, nomnoml) render these ``<pre>``
    elements at load time.
    """
    source = _MERMAID_FENCE_RE.sub(
        lambda m: _diagram_pre(m.group("body"), "mermaid"), source
    )
    return _NOMNOML_FENCE_RE.sub(
        lambda m: _diagram_pre(m.group("body"), "nomnoml"), source
    )


def diagram_engines(source: str) -> set[str]:
    """Return the diagram engines used in *source* (mermaid / nomnoml)."""
    engines: set[str] = set()
    if _MERMAID_FENCE_RE.search(source):
        engines.add("mermaid")
    if _NOMNOML_FENCE_RE.search(source):
        engines.add("nomnoml")
    return engines


def expand_for_revealjs(source: str) -> str:
    """Rewrite layout directives into reveal section classes.

    A ``<!-- layout: X -->`` comment that follows an ATX heading attaches
    ``.slide-X`` (and ``.center`` for centred layouts) to that heading so
    Pandoc emits the class on the reveal ``<section>``. Orphan directives
    are dropped. Everything else passes through untouched.
    """
    source = expand_diagrams(source)
    out: list[str] = []
    in_fence = False
    last_heading_idx = -1
    for line in source.splitlines():
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            continue
        if in_fence:
            out.append(line)
            continue
        m_layout = _LAYOUT_RE.match(line)
        if m_layout:
            if last_heading_idx >= 0:
                hm = _ATX_RE.match(out[last_heading_idx])
                if hm:
                    out[last_heading_idx] = _heading_with_layout(
                        hm.group("hashes"), hm.group("rest"),
                        m_layout.group("name"),
                    )
                last_heading_idx = -1
            continue  # drop the directive line
        if _ATX_RE.match(line):
            last_heading_idx = len(out)
        out.append(line)
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")


def _callout_to_blockquote(
    lines: list[str], start: int, match: re.Match[str]
) -> tuple[list[str], int]:
    """Convert a callout fenced div to a bold-titled blockquote.

    Returns the replacement lines and the number of source lines consumed.
    """
    kind = match.group("kind")
    attrs = match.group("attrs") or ""
    title_m = _TITLE_ATTR_RE.search(attrs)
    label = (
        title_m.group(1).strip()
        if title_m
        else _CALLOUT_LABELS.get(kind, kind.title())
    )
    body: list[str] = []
    depth = 1
    j = start + 1
    while j < len(lines):
        line = lines[j]
        if _DIV_OPEN_RE.match(line):
            depth += 1
            body.append(line)
        elif _DIV_CLOSE_RE.match(line):
            depth -= 1
            if depth == 0:
                j += 1
                break
            body.append(line)
        else:
            body.append(line)
        j += 1
    out = [f"> **{label}**", ">"]
    out.extend(("> " + b) if b.strip() else ">" for b in body)
    return out, j - start


def expand_for_pptx(source: str) -> str:
    """Prepare slide Markdown for Pandoc's PowerPoint writer.

    Drops reveal-only constructs (layout hints, ``. . .`` pauses,
    ``background-*`` heading attributes) and rewrites callouts to
    bold-titled blockquotes, which the pptx writer renders cleanly.
    """
    lines = source.splitlines()
    out: list[str] = []
    in_fence = False
    last_heading_idx = -1
    i = 0
    while i < len(lines):
        line = lines[i]
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            out.append(line)
            i += 1
            continue
        if in_fence:
            out.append(line)
            i += 1
            continue
        layout_m = _LAYOUT_RE.match(line)
        if layout_m:
            # A "section" divider is a ``##`` slide in the source (so reveal
            # stays linear); promote it to ``#`` here so Pandoc's pptx writer
            # picks the native "Section Header" layout.
            if layout_m.group("name") == "section" and last_heading_idx >= 0:
                hm = _ATX_RE.match(out[last_heading_idx])
                if hm:
                    rest = _TRAILING_ATTR_RE.sub("", hm.group("rest")).rstrip()
                    out[last_heading_idx] = f"# {rest}"
                last_heading_idx = -1
            i += 1
            continue
        if _PAUSE_RE.match(line):
            i += 1
            continue
        cm = _CALLOUT_OPEN_RE.match(line)
        if cm:
            block, consumed = _callout_to_blockquote(lines, i, cm)
            out.extend(block)
            i += consumed
            continue
        if _ATX_RE.match(line):
            if "background" in line:
                line = _BG_ATTR_RE.sub("", line)
            last_heading_idx = len(out)
        out.append(line)
        i += 1
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")
