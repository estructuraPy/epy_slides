"""Tests for SlideWindow export/print/CLI-GUI flows.

These drive the PDF/PowerPoint/print handlers and the ``_run_gui`` boot
path. The Qt boundaries that would block headlessly (file dialogs, the
asynchronous reveal->PDF print, the system print dialog, ``app.exec``) are
monkeypatched so the surrounding controller logic runs synchronously without
a real Chromium render or a real event loop.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings

from epy_slides import app as app_module
from epy_slides.app import SlideWindow, _run_gui
from epy_slides.tab import MarkdownTab


@pytest.fixture(scope="session", autouse=True)
def _isolate_qsettings(tmp_path_factory):
    """Redirect INI QSettings to a temp dir for the whole session."""
    cfg = tmp_path_factory.mktemp("qsettings_export")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(cfg)
    )
    return cfg


@pytest.fixture
def window(qapp):
    """Build a SlideWindow and clean up its tabs afterwards."""
    win = SlideWindow()
    yield win
    for i in range(win.tabs.count()):
        widget = win.tabs.widget(i)
        if isinstance(widget, MarkdownTab):
            widget.cleanup_preview_tmp()
    win.deleteLater()


# --------------------------------------------------------------- export pptx


def test_export_pptx_writes_file(window, tmp_path, monkeypatch):
    deck = tmp_path / "deck.md"
    deck.write_text("## A\n\n- one\n", encoding="utf-8")
    window.open_path(deck)
    out = tmp_path / "deck.pptx"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    window._export_pptx()
    assert out.is_file()
    assert out.read_bytes()[:2] == b"PK"


def test_export_pptx_cancelled_is_noop(window, monkeypatch):
    window._new_tab()
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    window._export_pptx()  # cancelled → no exception


def test_export_pptx_appends_extension(window, tmp_path, monkeypatch):
    window._current_tab().set_initial_text("## A\n")
    target = tmp_path / "noext"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    window._export_pptx()
    assert (tmp_path / "noext.pptx").is_file()


def test_export_pptx_reports_failure(window, tmp_path, monkeypatch):
    window._current_tab().set_initial_text("## A\n")
    out = tmp_path / "x.pptx"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )

    def boom(*a, **k):
        raise RuntimeError("pandoc exploded")

    monkeypatch.setattr(app_module, "export_pptx", boom)
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "critical",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._export_pptx()
    assert warned["n"] == 1


def test_export_pptx_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._export_pptx()  # must not raise


# --------------------------------------------------------------- export pdf


def test_export_pdf_invokes_tab_export(window, tmp_path, monkeypatch):
    deck = tmp_path / "deck.md"
    deck.write_text("## A\n", encoding="utf-8")
    window.open_path(deck)
    out = tmp_path / "deck.pdf"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    captured: dict = {}

    def fake_export_pdf(self, target, on_done):
        captured["target"] = target
        on_done(target, True)

    monkeypatch.setattr(MarkdownTab, "export_pdf", fake_export_pdf)
    window._export_pdf()
    assert captured["target"] == out


def test_export_pdf_appends_extension(window, tmp_path, monkeypatch):
    window._current_tab().set_initial_text("## A\n")
    target = tmp_path / "slides"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    captured: dict = {}
    monkeypatch.setattr(
        MarkdownTab, "export_pdf",
        lambda self, target, on_done: captured.update(t=target),
    )
    window._export_pdf()
    assert captured["t"] == target.with_suffix(".pdf")


def test_export_pdf_cancelled_is_noop(window, monkeypatch):
    window._new_tab()
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    called = {"n": 0}
    monkeypatch.setattr(
        MarkdownTab, "export_pdf",
        lambda self, *a, **k: called.update(n=called["n"] + 1),
    )
    window._export_pdf()
    assert called["n"] == 0


def test_export_pdf_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._export_pdf()  # must not raise


def test_on_pdf_done_success_sets_status(window):
    window._on_pdf_done(Path("out.pdf"), True)
    # Status text reflects success; the call must not raise.
    assert "out.pdf" in window.statusBar().currentMessage()


def test_on_pdf_done_failure_warns(window, monkeypatch):
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._on_pdf_done(Path("bad.pdf"), False)
    assert warned["n"] == 1


# --------------------------------------------------------------- print


def test_print_document_accepted_calls_page_print(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## A\n")
    from PySide6.QtPrintSupport import QPrintDialog

    monkeypatch.setattr(
        QPrintDialog, "exec",
        lambda self: QPrintDialog.DialogCode.Accepted,
    )
    printed: dict = {}

    class _FakePage:
        def print(self, printer, cb):  # noqa: A003
            printed["ok"] = True
            cb(True)

    monkeypatch.setattr(tab.view, "page", lambda: _FakePage())
    window._print_document()
    assert printed["ok"] is True


def test_print_document_cancelled_is_noop(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## A\n")
    from PySide6.QtPrintSupport import QPrintDialog

    monkeypatch.setattr(
        QPrintDialog, "exec",
        lambda self: QPrintDialog.DialogCode.Rejected,
    )
    called = {"n": 0}

    class _FakePage:
        def print(self, *a, **k):  # noqa: A003
            called["n"] += 1

    monkeypatch.setattr(tab.view, "page", lambda: _FakePage())
    window._print_document()
    assert called["n"] == 0


def test_print_document_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._print_document()  # must not raise


# --------------------------------------------------------------- _run_gui


def test_run_gui_boots_and_opens_files(monkeypatch, tmp_path):
    # _run_gui builds a QApplication, shows the window and runs the event
    # loop. Patch the app class and exec so nothing blocks; assert the
    # existing deck on disk is opened and the loop's return code propagates.
    deck = tmp_path / "boot.md"
    deck.write_text("## Boot\n", encoding="utf-8")
    missing = tmp_path / "ghost.md"

    opened: list[Path] = []
    shown = {"n": 0}

    class _FakeApp:
        def __init__(self, *_a, **_k):
            pass

        def setWindowIcon(self, *_a):  # noqa: N802
            pass

        def exec(self):  # noqa: A003
            return 0

    class _FakeWindow:
        def show(self):
            shown["n"] += 1

        def open_path(self, p):
            opened.append(p)

    monkeypatch.setattr(app_module, "QApplication", _FakeApp)
    monkeypatch.setattr(app_module, "SlideWindow", lambda: _FakeWindow())
    monkeypatch.setattr(
        app_module, "_load_branding_pixmap", lambda name: _NullPixmap()
    )

    assert _run_gui([str(deck), str(missing)]) == 0
    assert shown["n"] == 1
    assert deck in opened
    assert missing not in opened


def test_run_gui_sets_window_icon_when_logo_present(monkeypatch):
    icon_set = {"n": 0}

    class _FakeApp:
        def __init__(self, *_a, **_k):
            pass

        def setWindowIcon(self, *_a):  # noqa: N802
            icon_set["n"] += 1

        def exec(self):  # noqa: A003
            return 3

    monkeypatch.setattr(app_module, "QApplication", _FakeApp)
    monkeypatch.setattr(
        app_module, "SlideWindow", lambda: type(
            "W", (), {"show": lambda self: None}
        )()
    )
    monkeypatch.setattr(
        app_module, "_load_branding_pixmap",
        lambda name: _NonNullPixmap(),
    )
    monkeypatch.setattr(app_module, "QIcon", lambda *a, **k: object())
    assert _run_gui([]) == 3
    assert icon_set["n"] == 1


class _NullPixmap:
    def isNull(self):  # noqa: N802  # matches the Qt API surface being faked
        return True


class _NonNullPixmap:
    def isNull(self):  # noqa: N802  # matches the Qt API surface being faked
        return False
