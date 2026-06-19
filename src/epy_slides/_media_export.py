"""Rasterize Mermaid / nomnoml diagrams to PNG for the PPTX export.

PowerPoint has no diagram engine, so a deck exported straight to ``.pptx``
would show its diagrams as raw source code. This module renders each diagram
the same way the live preview does — the bundled engines inside an offscreen
Qt WebEngine page — and grabs the result as a PNG, so the exported slides
carry the real picture, themed to match the deck.

Everything is best-effort: with no running ``QApplication`` (or on any
rendering error) the helpers return ``None`` for that diagram and the export
falls back to the source text, so they never break a headless conversion.
"""

from __future__ import annotations

import re
from pathlib import Path

# A fenced ```mermaid / ```nomnoml block, capturing the engine and its body
# in document order (so the i-th match maps to the i-th rendered image).
_ANY_DIAGRAM_RE = re.compile(
    r"^[ \t]*`{3,}[ \t]*\{?\.?(?P<engine>mermaid|nomnoml)[^\n}]*\}?[ \t]*\n"
    r"(?P<body>.*?)\n[ \t]*`{3,}[ \t]*$",
    re.MULTILINE | re.DOTALL,
)


def collect_diagrams(source: str) -> list[tuple[str, str]]:
    """Return ``(engine, body)`` for each diagram in document order."""
    return [
        (m.group("engine"), m.group("body"))
        for m in _ANY_DIAGRAM_RE.finditer(source)
    ]


def _diagram_page_html(
    diagrams: list[tuple[str, str]], theme_css: str
) -> str:
    """Build a minimal offscreen page that renders every diagram, themed."""
    from epy_slides.template import (  # noqa: PLC0415
        _MERMAID_CONFIG,
        _NOMNOML_CONFIG,
        _load_diagram_script,
    )

    engines = {e for e, _ in diagrams}
    head = ""
    inits = []
    if "mermaid" in engines:
        head += _load_diagram_script("mermaid") + _MERMAID_CONFIG
        inits.append("window._epy_init_mermaid()")
    if "nomnoml" in engines:
        head += _load_diagram_script("nomnoml") + _NOMNOML_CONFIG
        inits.append("window._epy_init_nomnoml()")

    blocks = []
    for i, (engine, body) in enumerate(diagrams):
        esc = (
            body.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        blocks.append(
            f'<div class="diagram" id="d{i}">'
            f'<pre class="{engine}">\n{esc}\n</pre></div>'
        )
    runner = (
        "<script>window._md = false;\n"
        "Promise.all([" + ", ".join(inits) + "])"
        ".then(function () { window._md = true; })"
        ".catch(function () { window._md = true; });</script>"
    )
    return (
        "<!doctype html><html><head><meta charset='utf-8'>\n"
        "<style>\n"
        f"{theme_css}\n"
        "body { margin: 0; background: #ffffff; }\n"
        ".diagram { display: inline-block; padding: 14px; }\n"
        ".diagram svg { display: block; }\n"
        "</style>\n"
        f"{head}\n</head><body>\n"
        + "\n".join(blocks)
        + f"\n{runner}\n</body></html>"
    )


_RECTS_JS = (
    "(function () {"
    "  var out = [];"
    "  document.querySelectorAll('.diagram').forEach(function (d) {"
    "    var svg = d.querySelector('svg') || d;"
    "    var r = svg.getBoundingClientRect();"
    "    out.push([r.left, r.top, r.width, r.height]);"
    "  });"
    "  return JSON.stringify(out);"
    "})()"
)


def render_diagram_pngs(
    diagrams: list[tuple[str, str]],
    out_dir: Path,
    *,
    theme_css: str = "",
    timeout_ms: int = 10000,
) -> list[Path | None]:
    """Render each diagram to a PNG in ``out_dir``; ``None`` on failure.

    Requires a running ``QApplication`` (the GUI export provides one). The
    diagrams are rendered together in one offscreen page and each is cropped
    out of a single grab, themed by ``theme_css`` (the deck's ``--epy-*``
    variables). Returns one entry per input diagram, in order.
    """
    if not diagrams:
        return []
    try:
        import json  # noqa: PLC0415

        from PySide6.QtCore import (  # noqa: PLC0415
            QElapsedTimer,
            QEventLoop,
            QRect,
            Qt,
            QUrl,
        )
        from PySide6.QtWebEngineWidgets import (  # noqa: PLC0415
            QWebEngineView,
        )
        from PySide6.QtWidgets import QApplication  # noqa: PLC0415
    except ImportError:
        return [None] * len(diagrams)

    app = QApplication.instance()
    if app is None:
        return [None] * len(diagrams)

    out_dir.mkdir(parents=True, exist_ok=True)
    results: list[Path | None] = [None] * len(diagrams)
    view = QWebEngineView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.resize(1400, 2200)
    view.show()

    def pump(ms: int) -> None:
        timer = QElapsedTimer()
        timer.start()
        while timer.elapsed() < ms:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)

    def js(expr: str) -> object:
        box: dict[str, object] = {"v": None}
        view.page().runJavaScript(expr, lambda v: box.__setitem__("v", v))
        timer = QElapsedTimer()
        timer.start()
        while box["v"] is None and timer.elapsed() < 4000:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
        return box["v"]

    try:
        loaded: dict[str, bool] = {"ok": False}
        view.loadFinished.connect(
            lambda ok: loaded.__setitem__("ok", ok)
        )
        # The engine bundles are megabytes; ``setHtml`` is capped at 2 MB and
        # would truncate them, so write the page to a file and load it.
        page_file = out_dir / "_diagram_page.html"
        page_file.write_text(
            _diagram_page_html(diagrams, theme_css), encoding="utf-8"
        )
        view.load(QUrl.fromLocalFile(str(page_file.resolve())))
        timer = QElapsedTimer()
        timer.start()
        while not loaded["ok"] and timer.elapsed() < timeout_ms:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
        # Wait for the engines to finish (window._md), then let layout settle.
        while (
            js("window._md === true") is not True
            and timer.elapsed() < timeout_ms
        ):
            pump(100)
        pump(250)

        raw = js(_RECTS_JS)
        rects = json.loads(raw) if isinstance(raw, str) else []
        pix = view.grab()
        scale = pix.width() / max(1, view.width())
        for i, rect in enumerate(rects):
            if i >= len(diagrams):
                break
            x, y, w, h = (v * scale for v in rect)
            if w < 2 or h < 2:
                continue
            crop = pix.copy(
                QRect(round(x), round(y), round(w), round(h))
            )
            png = out_dir / f"diagram_{i}.png"
            if crop.save(str(png)):
                results[i] = png
    except (OSError, RuntimeError, ValueError):
        pass
    finally:
        view.deleteLater()
        pump(20)
    return results


def substitute_diagram_images(
    source: str, pngs: list[Path | None]
) -> str:
    """Replace each diagram fence with an image link to its rendered PNG.

    Diagrams whose PNG is ``None`` (render failed) are left as their source
    fence, so the export still shows something readable.
    """
    index = [0]

    def repl(match: re.Match[str]) -> str:
        i = index[0]
        index[0] += 1
        png = pngs[i] if i < len(pngs) else None
        if png is None:
            return match.group(0)
        return f"![]({png.as_posix()})"

    return _ANY_DIAGRAM_RE.sub(repl, source)
