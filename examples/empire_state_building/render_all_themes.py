"""Render ``empire_state_building.md`` once per epy_slides theme.

From the single Markdown deck, each theme is exported to three formats:

  * **HTML** — a continuous reveal.js scroll view (a shareable web page,
    not a click-through slideshow).
  * **PPTX** — PowerPoint via Pandoc, using the per-theme reference deck so
    the slides carry the theme's colours and fonts.
  * **PDF**  — reveal.js print mode, one slide per landscape page, with the
    document metadata and the grayscale watermark stamped in.

Run it from this directory::

    python render_all_themes.py            # every theme
    python render_all_themes.py corporate  # a single theme

Output lands in ``_render/themes/`` (git-ignored). The PDF step drives Qt
WebEngine, so it needs a display or an offscreen Qt platform
(``QT_QPA_PLATFORM=offscreen``).
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QMarginsF, QSizeF, Qt, QTimer, QUrl
from PySide6.QtGui import QPageLayout, QPageSize
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parent

# Prefer an installed epy_slides; fall back to the in-repo source tree so the
# example runs straight from a clone without `pip install -e .`.
try:
    from epy_slides import themes
    from epy_slides._pdf_footer import add_metadata, add_watermark
    from epy_slides._revealjs_theme import reveal_css_for
    from epy_slides.renderer import export_pptx, render_revealjs
    from epy_slides.snippets import parse_front_matter
except ImportError:
    sys.path.insert(0, str(ROOT.parent.parent / "src"))
    from epy_slides import themes
    from epy_slides._pdf_footer import add_metadata, add_watermark
    from epy_slides._revealjs_theme import reveal_css_for
    from epy_slides.renderer import export_pptx, render_revealjs
    from epy_slides.snippets import parse_front_matter

SOURCE = ROOT / "empire_state_building.md"
OUT_DIR = ROOT / "_render" / "themes"


def _page_layout(meta: dict) -> QPageLayout:
    """Landscape, zero-margin page sized to the deck's aspect ratio."""
    aspect = (meta.get("aspect-ratio") or "16:9").strip()
    width_in, height_in = (10.0, 7.5) if aspect == "4:3" else (13.333, 7.5)
    size = QPageSize(
        QSizeF(width_in, height_in),
        QPageSize.Unit.Inch,
        "slide",
        QPageSize.SizeMatchPolicy.ExactMatch,
    )
    return QPageLayout(
        size,
        QPageLayout.Orientation.Portrait,
        QMarginsF(0.0, 0.0, 0.0, 0.0),
        QPageLayout.Unit.Inch,
    )


class SlideExporter:
    """Export one theme: HTML + PPTX synchronously, then PDF via WebEngine."""

    MAX_WAIT_MS = 60_000
    POLL_MS = 200

    def __init__(self, theme_id: str, source: str, meta: dict, on_done) -> None:
        self.theme_id = theme_id
        self.source = source
        self.meta = meta
        self.on_done = on_done
        self.pdf_path = OUT_DIR / f"empire_state_{theme_id}.pdf"
        self._tmp_html = ROOT / f"_tmp_{theme_id}.html"
        self._elapsed = 0

        self.view = QWebEngineView()
        # WA_DontShowOnScreen lays the view out offscreen so reveal's
        # print layout is measured without a visible window.
        self.view.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        self.view.resize(960, 700)
        self.view.show()

    def go(self) -> None:
        print(f"\n=== theme: {self.theme_id} ===")
        theme = themes.get(self.theme_id)
        css = reveal_css_for(theme)

        html = render_revealjs(
            self.source, base_dir=ROOT, theme_css=css,
            for_export=True, continuous=True,
        )
        html_path = OUT_DIR / f"empire_state_{self.theme_id}.html"
        html_path.write_text(html, encoding="utf-8")
        print(f"  HTML  -> {html_path.name}  ({len(html):,} chars)")

        pptx_path = OUT_DIR / f"empire_state_{self.theme_id}.pptx"
        try:
            export_pptx(
                self.source, pptx_path, base_dir=ROOT, theme_id=self.theme_id
            )
            print(f"  PPTX  -> {pptx_path.name}  "
                  f"({pptx_path.stat().st_size:,} bytes)")
        except (OSError, RuntimeError) as exc:
            print(f"  PPTX  FAILED: {exc}")

        # PDF: the paginated deck (NOT continuous) printed via reveal's
        # print-pdf mode, one slide per page.
        export_html = render_revealjs(
            self.source, base_dir=ROOT, theme_css=css, for_export=True
        )
        self._tmp_html.write_text(export_html, encoding="utf-8")
        self.view.loadFinished.connect(
            self._on_load, Qt.ConnectionType.SingleShotConnection
        )
        url = QUrl.fromLocalFile(str(self._tmp_html.resolve()))
        url.setQuery("print-pdf")
        self.view.load(url)

    def _on_load(self, ok: bool) -> None:
        if not ok:
            print(f"  [{self.theme_id}] load failed")
            self._finish()
            return
        self._elapsed = 0
        QTimer.singleShot(self.POLL_MS, self._poll)

    def _poll(self) -> None:
        self._elapsed += self.POLL_MS
        self.view.page().runJavaScript(
            "window._reveal_done === true && window._mathjax_done === true"
            " && window._diagrams_done === true",
            self._on_poll,
        )

    def _on_poll(self, done: object) -> None:
        if done is True or self._elapsed >= self.MAX_WAIT_MS:
            QTimer.singleShot(self.POLL_MS, self._do_print)
        else:
            QTimer.singleShot(self.POLL_MS, self._poll)

    def _do_print(self) -> None:
        self.view.page().pdfPrintingFinished.connect(
            self._on_printed, Qt.ConnectionType.SingleShotConnection
        )
        self.view.page().printToPdf(str(self.pdf_path), _page_layout(self.meta))

    def _on_printed(self, _path: str, ok: bool) -> None:
        if ok and self.pdf_path.exists():
            try:
                watermark = str(self.meta.get("watermark", "") or "").strip()
                if watermark and (ROOT / watermark).is_file():
                    add_watermark(self.pdf_path, ROOT / watermark)
                add_metadata(
                    self.pdf_path,
                    title=str(self.meta.get("title", "")),
                    author=str(self.meta.get("author", "")),
                    subject=str(self.meta.get("subtitle", "")),
                    rights=str(self.meta.get("copyright", "")),
                )
            except (OSError, RuntimeError) as exc:
                print(f"  [{self.theme_id}] overlay error: {exc}")
            print(f"  PDF   -> {self.pdf_path.name}  "
                  f"({self.pdf_path.stat().st_size:,} bytes)")
        else:
            print(f"  [{self.theme_id}] PDF print failed")
        self._finish()

    def _finish(self) -> None:
        try:
            self._tmp_html.unlink(missing_ok=True)
        except OSError:
            pass
        self.on_done()


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = SOURCE.read_text(encoding="utf-8")
    meta = parse_front_matter(source)

    app = QApplication.instance() or QApplication(sys.argv)
    only = sys.argv[1] if len(sys.argv) > 1 else None
    remaining = [only] if only else list(themes.THEMES.keys())

    def kick_next() -> None:
        if not remaining:
            print("\nAll themes rendered.")
            app.quit()
            return
        theme_id = remaining.pop(0)
        exporter = SlideExporter(theme_id, source, meta, on_done=kick_next)
        main._current = exporter  # type: ignore[attr-defined]
        exporter.go()

    QTimer.singleShot(0, kick_next)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
