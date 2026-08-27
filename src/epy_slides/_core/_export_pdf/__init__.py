"""Headless reveal.js -> PDF rendering for the scriptable API.

Encapsulates the offscreen Qt WebEngine print flow (one slide per page,
metadata + grayscale watermark stamped in) so ``SlideDeck.to_pdf`` works
without the GUI. Requires PySide6; safe to import without it (the Qt import
is deferred to call time).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path


def _scale_pdf(pdf_path: Path, target_width_in: float) -> None:
    """Scale every page of ``pdf_path`` to ``target_width_in`` (vector-safe).

    reveal sizes the print page to the 960 px deck, which Qt prints a touch
    under the 16:9 PowerPoint size; the exact printed width also drifts a few
    percent from the requested page layout. Scaling the finished *vector* PDF
    to the target width (computed per page from its real media box, so the
    drift is absorbed) keeps the text crisp and gives the deck the larger
    widescreen sheet. The aspect ratio is preserved (one uniform scale).
    """
    from pypdf import PdfWriter  # noqa: PLC0415

    target_pt = target_width_in * 72.0
    # Clone (not reader -> fresh writer): a fresh PdfWriter drops the
    # document catalog, killing link annotations' named destinations.
    writer = PdfWriter(clone_from=str(pdf_path))
    for page in writer.pages:
        width_pt = float(page.mediabox.width)
        if width_pt > 0:
            page.scale_by(target_pt / width_pt)
    with pdf_path.open("wb") as handle:
        writer.write(handle)


def _readiness_report(js: Callable[[str], object]) -> str:
    """Say which readiness signal never came up.

    Reached only on failure, so four extra JS round-trips cost nothing
    that matters, and the message is the difference between "the deck
    came out blank" and knowing whether reveal, MathJax, the diagrams
    or the per-page wrappers were the one still missing.
    """
    parts = [
        f"window.{flag}={js('window.' + flag)!r}"
        for flag in ("_reveal_done", "_mathjax_done", "_diagrams_done")
    ]
    count = js('document.querySelectorAll(".pdf-page").length')
    parts.append(f"pdf-page count={count!r}")
    return "deck never became ready to print (" + ", ".join(parts) + ")"


def _remove_temp(tmp: Path, pump: Callable[[int], None]) -> None:
    """Delete the staged HTML, waiting for the engine to release it.

    On Windows the web engine can still hold the file it loaded some
    hundreds of milliseconds after the view is scheduled for deletion.
    The unlink then raises WinError 32 from inside a ``finally``, which
    REPLACES whatever the export was about to report: a real render
    failure surfaced as a file-locking error. Measured on a 3 MB deck,
    that is exactly how one blank export was reported.

    Retry briefly, then give up quietly. A leftover temporary file is
    not worth losing the outcome over.
    """
    for _ in range(20):
        try:
            tmp.unlink(missing_ok=True)
            return
        except OSError:
            pump(100)


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

    from epy_slides._core import _pdf_footer  # noqa: PLC0415
    from epy_slides._core.renderer import render_revealjs  # noqa: PLC0415
    from epy_slides._core.snippets import parse_front_matter  # noqa: PLC0415
    from epy_slides._core.template import watermark_pdf_params  # noqa: PLC0415

    meta = parse_front_matter(source)
    aspect = (meta.get("aspect-ratio") or "16:9").strip()
    # Match reveal's PDF page pixel size at 96 px/inch (960x540 / 960x720).
    width_in, height_in = (10.0, 7.5) if aspect == "4:3" else (10.0, 5.625)
    # The 16:9 page reveal produces reads small next to a PowerPoint deck;
    # after printing, scale the vector PDF to the 13.333 in widescreen width
    # (crisp — it is vector). 4:3 already prints at the 10x7.5 in PowerPoint
    # size, so it is left as-is.
    pdf_target_w = None if aspect == "4:3" else 13.333

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
        # A clock per wait. One shared clock made every later budget the
        # leftover of the earlier stage, so a slow load bought the
        # readiness wait nothing -- and what that produces is a blank
        # deck reported as a success, which is the failure below.
        load_clock = QElapsedTimer()
        load_clock.start()
        while not loaded["ok"] and load_clock.elapsed() < timeout_ms:
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
        # In print-pdf mode the flags flip true as soon as reveal initialises,
        # but the per-page .pdf-page wrappers are built one frame later — wait
        # for them too, or the print captures a single blank page.
        ready_js = (
            "window._reveal_done === true && window._mathjax_done === true"
            " && window._diagrams_done === true"
            " && document.querySelectorAll('.pdf-page').length > 0"
        )
        ready_clock = QElapsedTimer()
        ready_clock.start()
        while js(ready_js) is not True and ready_clock.elapsed() < timeout_ms:
            pump(150)
        # An ASSERTION, not a wait. Measured: with the readiness wait
        # given no budget, reveal reports nothing, .pdf-page count is 0,
        # the print goes ahead and Chromium reports SUCCESS -- because
        # printing nothing is a successful print. The check below cannot
        # tell that apart, so a one-page blank deck shipped as done.
        if js(ready_js) is not True:
            raise RuntimeError(_readiness_report(js))
        pump(200)

        def on_printed(_p: str, ok: bool) -> None:
            state["ok"] = ok
            state["printed"] = True

        view.page().pdfPrintingFinished.connect(on_printed)
        view.page().printToPdf(str(out_path), layout)
        print_clock = QElapsedTimer()
        print_clock.start()
        while (
            not state["printed"]
            and print_clock.elapsed() < timeout_ms + 10000
        ):
            app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 30)
    finally:
        view.deleteLater()
        pump(20)
        _remove_temp(tmp, pump)

    if not (state["ok"] and out_path.exists()):
        raise RuntimeError("PDF export failed (reveal/print did not complete)")

    if pdf_target_w is not None:
        _scale_pdf(out_path, pdf_target_w)

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
