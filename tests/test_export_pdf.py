"""Tests for the headless reveal.js -> PDF flow in ``_export_pdf``.

The real export drives an offscreen Qt WebEngine page and a live Chromium
print, which hangs for minutes in this environment. Here the Qt boundary is
monkeypatched so the surrounding logic in :func:`render_deck_pdf` runs
synchronously without Chromium: the fake view reports a finished load, the
``runJavaScript`` readiness probe returns ``True`` immediately, and
``printToPdf`` writes a real reportlab PDF and fires ``pdfPrintingFinished``.
That lets the metadata/watermark stamping (our code) run on a genuine PDF.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")

from epy_slides import _export_pdf  # noqa: E402


def _write_real_pdf(path: str) -> None:
    """Write a tiny one-page PDF with reportlab so pypdf can read it back."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=A4)
    pdf.drawString(72, 720, "Slide body")
    pdf.showPage()
    pdf.save()


class _FakeSignal:
    """A minimal Qt-signal stand-in that stores the connected slot."""

    def __init__(self) -> None:
        self.slot = None

    def connect(self, slot, *args, **kwargs) -> None:
        self.slot = slot


class _FakePage:
    """Fake QWebEnginePage: synchronous JS + an in-process printToPdf."""

    def __init__(self) -> None:
        self.pdfPrintingFinished = _FakeSignal()  # noqa: N815 (Qt name)

    def runJavaScript(self, _expr, callback) -> None:  # noqa: N802
        # The readiness probe and any other JS resolve to True at once.
        callback(True)

    def printToPdf(self, path, _layout) -> None:  # noqa: N802
        _write_real_pdf(path)
        if self.pdfPrintingFinished.slot is not None:
            self.pdfPrintingFinished.slot(path, True)


class _FakeView:
    """Fake QWebEngineView that fires loadFinished immediately on load."""

    def __init__(self) -> None:
        self.loadFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._page = _FakePage()
        self._deleted = False

    def setAttribute(self, *_a, **_k) -> None:  # noqa: N802
        pass

    def resize(self, *_a) -> None:
        pass

    def show(self) -> None:
        pass

    def page(self):
        return self._page

    def load(self, _url) -> None:
        if self.loadFinished.slot is not None:
            self.loadFinished.slot(True)

    def deleteLater(self) -> None:  # noqa: N802
        self._deleted = True


class _FakeApp:
    """Fake QApplication: processEvents is a no-op so the pumps exit fast."""

    def __init__(self, *_a, **_k) -> None:
        pass

    def processEvents(self, *_a, **_k) -> None:  # noqa: N802
        pass


class _DeferredApp:
    """Fake QApplication whose processEvents drains one queued action.

    The view enqueues its signal/JS resolutions instead of firing them
    synchronously, so the ``while ... processEvents`` polling loops in
    :func:`render_deck_pdf` actually iterate at least once each.
    """

    def __init__(self, *_a, **_k) -> None:
        self.queue: list = []

    def processEvents(self, *_a, **_k) -> None:  # noqa: N802
        if self.queue:
            self.queue.pop(0)()


class _DeferredPage:
    """Page whose JS first returns ``None`` then ``True`` via the queue."""

    def __init__(self, app: _DeferredApp) -> None:
        self.app = app
        self.pdfPrintingFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._ready_calls = 0

    def runJavaScript(self, expr, callback) -> None:  # noqa: N802
        # Every probe defers its result by one processEvents so the js()
        # poll-loop body runs at least once. The readiness probe reports
        # "not ready" on the first poll so the outer readiness loop body
        # (pump) executes too, then becomes ready.
        if "_reveal_done" in expr:
            self._ready_calls += 1
            value = self._ready_calls >= 2
        else:
            value = True
        self.app.queue.append(lambda: callback(value))

    def printToPdf(self, path, _layout) -> None:  # noqa: N802
        # Defer the finished signal so the print-wait loop body executes.
        def finish() -> None:
            _write_real_pdf(path)
            if self.pdfPrintingFinished.slot is not None:
                self.pdfPrintingFinished.slot(path, True)

        self.app.queue.append(finish)


class _DeferredView:
    """View that defers loadFinished so the load-wait loop body runs."""

    def __init__(self, app: _DeferredApp) -> None:
        self.app = app
        self.loadFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._page = _DeferredPage(app)

    def setAttribute(self, *_a, **_k) -> None:  # noqa: N802
        pass

    def resize(self, *_a) -> None:
        pass

    def show(self) -> None:
        pass

    def page(self):
        return self._page

    def load(self, _url) -> None:
        def fire() -> None:
            if self.loadFinished.slot is not None:
                self.loadFinished.slot(True)

        self.app.queue.append(fire)

    def deleteLater(self) -> None:  # noqa: N802
        pass


@pytest.fixture
def patched_qt(monkeypatch):
    """Patch the Qt classes used by ``render_deck_pdf`` to fakes."""
    from PySide6 import QtWebEngineWidgets, QtWidgets

    view = _FakeView()
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    return view


_DECK = (
    "---\ntitle: Export Deck\nauthor: ANM\nsubtitle: Sub\n"
    "copyright: (c) ANM\n---\n\n## One\n\n- a\n\n## Two\n\ntext\n"
)


def test_render_deck_pdf_writes_pdf_and_stamps_metadata(
    qapp, patched_qt, tmp_path
):
    out = tmp_path / "deck.pdf"
    _export_pdf.render_deck_pdf(
        _DECK, out, base_dir=tmp_path, theme_css="", timeout_ms=2000
    )
    assert out.is_file()
    from pypdf import PdfReader

    reader = PdfReader(str(out))
    meta = reader.metadata
    assert meta is not None
    assert meta.title == "Export Deck"
    assert meta.author == "ANM"


def test_render_deck_pdf_4x3_aspect_ratio(qapp, patched_qt, tmp_path):
    # The 4:3 branch picks a 10x7.5in page; only the page-size selection
    # differs, so assert the export still produces a readable PDF.
    deck = "---\ntitle: Wide\naspect-ratio: \"4:3\"\n---\n\n## A\n\nx\n"
    out = tmp_path / "fourthree.pdf"
    _export_pdf.render_deck_pdf(
        deck, out, base_dir=tmp_path, theme_css="", timeout_ms=2000
    )
    assert out.is_file()


def test_render_deck_pdf_applies_watermark(qapp, patched_qt, tmp_path):
    # A resolvable watermark file drives the add_watermark branch.
    pytest.importorskip("PIL")
    from PIL import Image

    wm = tmp_path / "wm.png"
    Image.new("RGBA", (8, 8), (200, 0, 0, 128)).save(wm)
    deck = (
        "---\ntitle: Marked\nwatermark: wm.png\n---\n\n## A\n\nx\n"
    )
    out = tmp_path / "marked.pdf"
    _export_pdf.render_deck_pdf(
        deck, out, base_dir=tmp_path, theme_css="", timeout_ms=2000
    )
    assert out.is_file()


def test_render_deck_pdf_raises_when_print_fails(
    qapp, monkeypatch, tmp_path
):
    # A page whose printToPdf never reports success must raise RuntimeError.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    class _FailPage(_FakePage):
        def printToPdf(self, path, _layout) -> None:  # noqa: N802
            if self.pdfPrintingFinished.slot is not None:
                self.pdfPrintingFinished.slot(path, False)

    class _FailView(_FakeView):
        def __init__(self) -> None:
            super().__init__()
            self._page = _FailPage()

    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: _FailView()
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    out = tmp_path / "nope.pdf"
    with pytest.raises(RuntimeError):
        _export_pdf.render_deck_pdf(
            _DECK, out, base_dir=tmp_path, theme_css="", timeout_ms=200
        )


def test_render_deck_pdf_drives_polling_loops(
    qapp, monkeypatch, tmp_path
):
    # Drive the asynchronous poll loops: the deferred view resolves its
    # load/JS/print signals only on processEvents, so every ``while ...
    # processEvents`` body iterates at least once before completing.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    app = _DeferredApp()
    view = _DeferredView(app)
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: app)
    )
    out = tmp_path / "polled.pdf"
    _export_pdf.render_deck_pdf(
        _DECK, out, base_dir=tmp_path, theme_css="", timeout_ms=5000
    )
    assert out.is_file()


def test_render_deck_pdf_constructs_app_when_none(
    qapp, monkeypatch, tmp_path
):
    # When QApplication.instance() is None the function constructs one;
    # patch the class to a fake so no second real app is created.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    view = _FakeView()
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )

    class _FakeAppClass(_FakeApp):
        @staticmethod
        def instance():
            return None

    monkeypatch.setattr(QtWidgets, "QApplication", _FakeAppClass)
    out = tmp_path / "made.pdf"
    _export_pdf.render_deck_pdf(
        _DECK, out, base_dir=tmp_path, theme_css="", timeout_ms=2000
    )
    assert out.is_file()
