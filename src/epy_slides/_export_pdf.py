"""Headless reveal.js -> PDF rendering for the scriptable API.

Encapsulates the offscreen Qt WebEngine print flow (one slide per page,
metadata + grayscale watermark stamped in) so ``SlideDeck.to_pdf`` works
without the GUI. Requires PySide6; safe to import without it (the Qt import
is deferred to call time).
"""

from __future__ import annotations

from pathlib import Path


def render_deck_pdf(
    source: str,
    out_path: Path,
    *,
    base_dir: Path | None,
    theme_css: str,
    timeout_ms: int = 60000,
) -> None:
    """Render slide Markdown ``source`` to a one-slide-per-page PDF."""
    from PySide6.QtCore import (  # noqa: PLC0415
        QElapsedTimer,
        QEventLoop,
        QMarginsF,
        QSizeF,
        Qt,
        QUrl,
    )
    from PySide6.QtGui import QPageLayout, QPageSize  # noqa: PLC0415
    from PySide6.QtWebEngineWidgets import QWebEngineView  # noqa: PLC0415
    from PySide6.QtWidgets import QApplication  # noqa: PLC0415

    from epy_slides import _pdf_footer  # noqa: PLC0415
    from epy_slides.renderer import render_revealjs  # noqa: PLC0415
    from epy_slides.snippets import parse_front_matter  # noqa: PLC0415
    from epy_slides.template import watermark_pdf_params  # noqa: PLC0415

    meta = parse_front_matter(source)
    aspect = (meta.get("aspect-ratio") or "16:9").strip()
    # Match reveal's PDF page pixel size at 96 px/inch (960x540 / 960x720).
    width_in, height_in = (10.0, 7.5) if aspect == "4:3" else (10.0, 5.625)

    app = QApplication.instance() or QApplication([])
    html = render_revealjs(
        source, base_dir=base_dir, theme_css=theme_css, for_export=True
    )
    tmp = out_path.with_suffix(".tmp.html")
    tmp.write_text(html, encoding="utf-8")

    view = QWebEngineView()
    view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    view.resize(960, 700)
    view.show()

    size = QPageSize(
        QSizeF(width_in, height_in),
        QPageSize.Unit.Inch,
        "slide",
        QPageSize.SizeMatchPolicy.ExactMatch,
    )
    layout = QPageLayout(
        size, QPageLayout.Orientation.Portrait,
        QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Inch,
    )

    state = {"printed": False, "ok": False}

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
        loaded = {"ok": False}
        view.loadFinished.connect(lambda ok: loaded.__setitem__("ok", ok))
        url = QUrl.fromLocalFile(str(tmp.resolve()))
        url.setQuery("print-pdf")
        view.load(url)
        timer = QElapsedTimer()
        timer.start()
        while not loaded["ok"] and timer.elapsed() < timeout_ms:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
        ready_js = (
            "window._reveal_done === true && window._mathjax_done === true"
            " && window._diagrams_done === true"
        )
        while js(ready_js) is not True and timer.elapsed() < timeout_ms:
            pump(150)
        pump(200)

        def on_printed(_p: str, ok: bool) -> None:
            state["ok"] = ok
            state["printed"] = True

        view.page().pdfPrintingFinished.connect(on_printed)
        view.page().printToPdf(str(out_path), layout)
        while not state["printed"] and timer.elapsed() < timeout_ms + 10000:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
    finally:
        view.deleteLater()
        pump(20)
        tmp.unlink(missing_ok=True)

    if not (state["ok"] and out_path.exists()):
        raise RuntimeError("PDF export failed (reveal/print did not complete)")

    watermark = (meta.get("watermark") or "").strip()
    if watermark:
        wm = Path(watermark)
        if not wm.is_absolute() and base_dir is not None:
            wm = base_dir / watermark
        if wm.is_file():
            ratio, opacity = watermark_pdf_params(meta)
            _pdf_footer.add_watermark(
                out_path, wm, opacity=opacity, width_ratio=ratio
            )
    _pdf_footer.add_metadata(
        out_path,
        title=meta.get("title", ""),
        author=meta.get("author", ""),
        subject=meta.get("subtitle", ""),
        rights=meta.get("copyright", ""),
    )
