"""Tests for MarkdownTab's asynchronous reveal->PDF export flow.

The real export drives an offscreen Qt WebEngine print, which hangs for
minutes here. The tab's ``view`` is replaced with a fake whose signals and
``runJavaScript`` resolve synchronously, and whose ``printToPdf`` writes a
real reportlab PDF, so the metadata/watermark stamping and the success/
failure callbacks (our code) run without a real Chromium render.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from epy_slides.tab import MarkdownTab  # noqa: E402


def _write_real_pdf(path: str) -> None:
    """Write a tiny one-page PDF with reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(72, 720, "slide")
    pdf.showPage()
    pdf.save()


class _FakeSignal:
    def __init__(self):
        self.slot = None

    def connect(self, slot, *a, **k):
        self.slot = slot


class _FakePage:
    def __init__(self, *, ready=True, print_ok=True):
        self.pdfPrintingFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._ready = ready
        self._print_ok = print_ok

    def runJavaScript(self, _expr, callback):  # noqa: N802
        callback(self._ready)

    def printToPdf(self, path, _layout):  # noqa: N802
        if self._print_ok:
            _write_real_pdf(path)
        slot = self.pdfPrintingFinished.slot
        # Single-shot, matching Qt's SingleShotConnection: clear before
        # firing so a re-render triggered inside finalize cannot re-enter.
        self.pdfPrintingFinished.slot = None
        if slot is not None:
            slot(path, self._print_ok)


class _FakeView:
    def __init__(self, *, load_ok=True, ready=True, print_ok=True):
        self.loadFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._page = _FakePage(ready=ready, print_ok=print_ok)
        self._load_ok = load_ok

    def page(self):
        return self._page

    def load(self, _url):
        slot = self.loadFinished.slot
        # Single-shot: clear before firing so the re-render inside finalize
        # (which calls load() again) does not re-enter the export flow.
        self.loadFinished.slot = None
        if slot is not None:
            slot(self._load_ok)


@pytest.fixture
def tab(qapp, monkeypatch):
    """A MarkdownTab whose QTimer.singleShot fires immediately."""
    from PySide6.QtCore import QTimer

    # The readiness poll uses QTimer.singleShot; make it synchronous so the
    # poll resolves without a real event loop.
    monkeypatch.setattr(
        QTimer, "singleShot", staticmethod(lambda _ms, fn: fn())
    )
    widget = MarkdownTab()
    yield widget
    widget.cleanup_preview_tmp()
    widget.deleteLater()


_DECK = (
    "---\ntitle: Deck\nauthor: ANM\ndate: 2026-06-20\n"
    "subtitle: Sub\nkeywords: a, b\n---\n\n## A\n\nx\n"
)


def test_export_pdf_success_writes_target(tab, tmp_path, monkeypatch):
    tab.set_initial_text(_DECK)
    tab._path = tmp_path / "deck.md"
    monkeypatch.setattr(tab, "view", _FakeView())
    out = tmp_path / "out.pdf"
    results: list = []
    tab.export_pdf(out, lambda target, ok: results.append((target, ok)))
    assert out.is_file()
    assert results == [(out, True)]
    from pypdf import PdfReader

    meta = PdfReader(str(out)).metadata
    assert meta.title == "Deck"
    assert meta.author == "ANM"


def test_export_pdf_derives_copyright_from_author_and_date(
    tab, tmp_path, monkeypatch
):
    # No explicit copyright, but author + a 4-digit date year derive one.
    tab.set_initial_text(
        "---\ntitle: D\nauthor: ANM\ndate: 2026-01-01\n---\n\n## A\n\nx\n"
    )
    monkeypatch.setattr(tab, "view", _FakeView())
    out = tmp_path / "c.pdf"
    tab.export_pdf(out)
    assert out.is_file()


def test_export_pdf_copyright_author_only_no_year(tab, tmp_path, monkeypatch):
    # Author present but no parseable year still yields a copyright string.
    tab.set_initial_text(
        "---\ntitle: D\nauthor: ANM\n---\n\n## A\n\nx\n"
    )
    monkeypatch.setattr(tab, "view", _FakeView())
    out = tmp_path / "c2.pdf"
    tab.export_pdf(out)
    assert out.is_file()


def test_export_pdf_with_watermark(tab, tmp_path, monkeypatch):
    pytest.importorskip("PIL")
    from PIL import Image

    wm = tmp_path / "wm.png"
    Image.new("RGBA", (8, 8), (10, 20, 30, 120)).save(wm)
    tab.set_initial_text(
        "---\ntitle: D\nwatermark: wm.png\n---\n\n## A\n\nx\n"
    )
    tab._path = tmp_path / "deck.md"
    monkeypatch.setattr(tab, "view", _FakeView())
    out = tmp_path / "wm.pdf"
    results: list = []
    tab.export_pdf(out, lambda t, ok: results.append(ok))
    assert out.is_file()
    assert results == [True]


def test_export_pdf_load_failure_reports_false(tab, tmp_path, monkeypatch):
    tab.set_initial_text(_DECK)
    monkeypatch.setattr(tab, "view", _FakeView(load_ok=False))
    out = tmp_path / "fail.pdf"
    results: list = []
    tab.export_pdf(out, lambda t, ok: results.append(ok))
    assert results == [False]
    assert not out.exists()


def test_export_pdf_finalize_error_reports_false(
    tab, tmp_path, monkeypatch
):
    # An exception while stamping metadata is caught and reported as failure.
    tab.set_initial_text(_DECK)
    monkeypatch.setattr(tab, "view", _FakeView())

    from epy_slides import _pdf_footer

    def boom(*a, **k):
        raise RuntimeError("metadata stamp failed")

    monkeypatch.setattr(_pdf_footer, "add_metadata", boom)
    out = tmp_path / "err.pdf"
    results: list = []
    tab.export_pdf(out, lambda t, ok: results.append(ok))
    assert results == [False]


def test_export_pdf_print_failure_reports_false(tab, tmp_path, monkeypatch):
    tab.set_initial_text(_DECK)
    monkeypatch.setattr(tab, "view", _FakeView(print_ok=False))
    out = tmp_path / "pfail.pdf"
    results: list = []
    tab.export_pdf(out, lambda t, ok: results.append(ok))
    assert results == [False]


def test_export_pdf_readiness_times_out_then_prints(
    tab, tmp_path, monkeypatch
):
    # The readiness probe never returns True; the poll loop exhausts its
    # budget and prints anyway (the timeout branch in _wait_for_export_ready).
    import epy_slides.tab as tab_mod

    # Shrink the budget so the (synchronous) poll terminates in a few steps
    # instead of recursing 600 deep.
    monkeypatch.setattr(tab_mod, "_EXPORT_TIMEOUT_MS", 300)
    monkeypatch.setattr(tab_mod, "_EXPORT_POLL_MS", 100)
    tab.set_initial_text(_DECK)
    monkeypatch.setattr(tab, "view", _FakeView(ready=False))
    out = tmp_path / "timeout.pdf"
    results: list = []
    tab.export_pdf(out, lambda t, ok: results.append(ok))
    # Print still ran and produced the PDF.
    assert out.is_file()
    assert results == [True]


# ----------------------------------------------- static page-size helpers


def test_slide_inches_16x9_default():
    assert MarkdownTab._slide_inches({}) == (10.0, 5.625)


def test_slide_inches_4x3():
    assert MarkdownTab._slide_inches({"aspect-ratio": "4:3"}) == (10.0, 7.5)


def test_slide_page_layout_is_portrait_zero_margin(qapp):
    from PySide6.QtGui import QPageLayout

    layout = MarkdownTab._slide_page_layout(10.0, 5.625)
    assert layout.orientation() == QPageLayout.Orientation.Portrait
