"""Autosave contract of the epy_slides window, plus the export timer stop.

Every test says what breaks in the application if it fails. The
``QSettings`` constructor the window resolves is routed to a per-test INI
file by conftest (the two-argument constructor ignores
``setDefaultFormat`` and would otherwise write the real registry scope),
and the modal save prompt of ``closeEvent`` is bypassed at teardown
because a modal dialog does not fail under a headless run -- it hangs it.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from epy_slides import app as app_module
from epy_slides._ui import tab as tab_module
from epy_slides._ui.tab import MarkdownTab
from epy_slides.app import SlideWindow

ORIGINAL = "## A\n\n- one\n"


def _settings() -> Any:
    """The same scope the window writes to (per-test INI via conftest)."""
    return app_module.QSettings(app_module.ORGANIZATION, "epy_slides")


@pytest.fixture
def make_window(qapp: Any) -> Iterator[Callable[[], SlideWindow]]:
    """Build windows on a clean autosave setting; close them prompt-free."""
    windows: list[SlideWindow] = []

    def _make() -> SlideWindow:
        win = SlideWindow()
        windows.append(win)
        return win

    yield _make
    for win in windows:
        win._confirm_close = lambda _tab: True
        for i in range(win.tabs.count()):
            widget = win.tabs.widget(i)
            if isinstance(widget, MarkdownTab):
                widget.cleanup_preview_tmp()
        win.close()
        win.deleteLater()


def _open(win: SlideWindow, path: Path) -> MarkdownTab:
    """Open ``path`` (written with ``ORIGINAL`` if absent); return its tab."""
    if not path.exists():
        path.write_text(ORIGINAL, encoding="utf-8")
    win.open_path(path)
    tab = win._current_tab()
    assert tab is not None and tab.path == path
    return tab


def _edited(win: SlideWindow, path: Path) -> MarkdownTab:
    """Open ``path`` and put a dirty edit on top of it."""
    tab = _open(win, path)
    tab.editor.appendPlainText("edited")
    assert tab.dirty, "precondition: an edit marks the tab dirty"
    return tab


def _save_dialog(monkeypatch: pytest.MonkeyPatch, out: Path) -> None:
    """Make the save dialog answer ``out`` without opening."""
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *_args, **_kwargs: (str(out), "")),
    )


def test_autosave_off_by_default_writes_nothing(
    make_window: Callable[[], SlideWindow], tmp_path: Path
) -> None:
    """Off is the default and off means the timer never writes.

    If this fails a fresh install rewrites decks the person never asked to
    save.
    """
    win = make_window()
    path = tmp_path / "deck.md"
    tab = _edited(win, path)
    assert not win.act_autosave.isChecked()
    assert not win._autosave_timer.isActive()
    win._autosave_current()
    assert path.read_text(encoding="utf-8") == ORIGINAL
    assert tab.dirty


def test_autosave_on_writes_dirty_tab_with_path(
    make_window: Callable[[], SlideWindow], tmp_path: Path
) -> None:
    """On, with a path and dirty: disk changes and the flag clears.

    If this fails the option is inert.
    """
    win = make_window()
    path = tmp_path / "deck.md"
    tab = _edited(win, path)
    win.act_autosave.setChecked(True)
    win._autosave_current()
    written = path.read_text(encoding="utf-8")
    assert written != ORIGINAL and written.endswith("edited")
    assert not tab.dirty


def test_autosave_untitled_never_opens_dialog(
    make_window: Callable[[], SlideWindow], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A buffer without a path is skipped and no dialog opens.

    A fallback through ``_save_current`` raises here; in the app it would
    block the person typing behind a modal Save As every 30 s.
    """
    win = make_window()
    tab = win._new_tab()
    win.tabs.setCurrentWidget(tab)
    tab.editor.appendPlainText("edited")
    assert tab.dirty and tab.path is None

    def _no_dialog(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("a dialog opened")

    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName", staticmethod(_no_dialog)
    )
    win.act_autosave.setChecked(True)
    win._autosave_current()
    assert tab.dirty


def test_autosave_skips_when_export_in_flight(
    make_window: Callable[[], SlideWindow], tmp_path: Path
) -> None:
    """With an export in flight the timer does not write; after, it does.

    If this fails a timer tick rewrites the deck while an export reads it.
    """
    win = make_window()
    path = tmp_path / "deck.md"
    _edited(win, path)
    win.act_autosave.setChecked(True)
    win._exports_in_flight = 1
    win._autosave_current()
    assert path.read_text(encoding="utf-8") == ORIGINAL
    win._exports_in_flight = 0
    win._autosave_current()
    written = path.read_text(encoding="utf-8")
    assert written != ORIGINAL and written.endswith("edited")


def test_pdf_export_keeps_counter_raised_until_done(
    make_window: Callable[[], SlideWindow],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PDF counter stays raised across the async print, then drops on
    the FAILURE callback too.

    Lowered before the callback = a timer tick writes while Chromium
    prints; not lowered on failure = autosave silently dead for the
    session after one bad export.
    """
    win = make_window()
    tab = _open(win, tmp_path / "deck.md")
    out = tmp_path / "deck.pdf"
    _save_dialog(monkeypatch, out)
    handed: list[Path] = []
    monkeypatch.setattr(
        tab, "export_pdf", lambda target, _on_done: handed.append(target)
    )
    warnings: list[str] = []
    monkeypatch.setattr(
        app_module.QMessageBox,
        "warning",
        staticmethod(lambda *args, **_kwargs: warnings.append(str(args[2]))),
    )
    win._export_pdf()
    assert handed == [out]
    assert win._exports_in_flight == 1
    win._on_pdf_done(out, False)
    assert len(warnings) == 1
    assert win._exports_in_flight == 0


def test_pdf_export_lowers_counter_when_hand_off_raises(
    make_window: Callable[[], SlideWindow],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A hand-off that raises never reaches the callback, so it lowers the
    counter itself; otherwise autosave is dead until restart."""
    win = make_window()
    tab = _open(win, tmp_path / "deck.md")
    _save_dialog(monkeypatch, tmp_path / "deck.pdf")

    def _boom(_target: Path, _on_done: Any) -> None:
        raise RuntimeError("render failed")

    monkeypatch.setattr(tab, "export_pdf", _boom)
    with pytest.raises(RuntimeError):
        win._export_pdf()
    assert win._exports_in_flight == 0


def test_export_html_lowers_the_counter(
    make_window: Callable[[], SlideWindow],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The synchronous HTML export raises and lowers the counter too.

    Every export must take part: one that does not lets the timer write
    while it runs.
    """
    win = make_window()
    _open(win, tmp_path / "deck.md")
    out = tmp_path / "deck.html"
    _save_dialog(monkeypatch, out)
    win._export_html()
    assert out.is_file()
    assert win._exports_in_flight == 0


def test_export_pptx_lowers_the_counter_on_failure(
    make_window: Callable[[], SlideWindow],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The PowerPoint error path lowers the counter before it returns.

    A decrement placed after the early ``return`` leaves autosave disabled
    after every failed export.
    """
    win = make_window()
    _open(win, tmp_path / "deck.md")
    _save_dialog(monkeypatch, tmp_path / "deck.pptx")

    def _boom(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("no writer")

    monkeypatch.setattr(app_module, "export_pptx", _boom)
    errors: list[str] = []
    monkeypatch.setattr(
        app_module.QMessageBox,
        "critical",
        staticmethod(lambda *args, **_kwargs: errors.append(str(args[1]))),
    )
    win._export_pptx()
    assert errors == ["Export PowerPoint failed"]
    assert win._exports_in_flight == 0


def test_autosave_preference_persists(
    make_window: Callable[[], SlideWindow],
) -> None:
    """The choice survives reopening: a second window starts checked.

    ``trigger()`` is the user's click; it flips the box, persists the
    string and starts or stops the timer.
    """
    first = make_window()
    assert first._autosave_timer.interval() == app_module.AUTOSAVE_INTERVAL_MS
    first.act_autosave.trigger()
    assert _settings().value("autosave") == "true"
    assert first._autosave_timer.isActive()

    second = make_window()
    assert second.act_autosave.isChecked()
    assert second._autosave_timer.isActive()

    first.act_autosave.trigger()
    assert _settings().value("autosave") == "false"
    assert not first._autosave_timer.isActive()


def test_spanish_strings_exist() -> None:
    """Both new labels translate; a missing key shows English in Spanish."""
    from epy_slides._core._i18n import _ES

    assert _ES["Autosave"] == "Guardado automático"
    assert "{path}" in _ES["Autosaved: {path}"]


def test_export_pdf_stops_the_render_debounce(
    qapp: Any, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Starting a PDF export stops a pending preview re-render.

    A debounce that fires mid-export loads the live preview into the same
    view the export is printing from: printToPdf fails and no file is
    written. epy_reports stops it; epy_slides did not.
    """
    (tmp_path / "pdf").mkdir()
    monkeypatch.setattr(
        tab_module.tempfile, "mkdtemp", lambda **_kw: str(tmp_path / "pdf")
    )
    tab = MarkdownTab()
    try:
        tab.editor.setPlainText(ORIGINAL)
        tab._render_timer.start()
        assert tab._render_timer.isActive()
        # No Chromium load: the export stops at the hand-off to the view.
        monkeypatch.setattr(tab.view, "load", lambda *_args: None)
        tab.export_pdf(tmp_path / "deck.pdf")
        assert not tab._render_timer.isActive()
    finally:
        tab.cleanup_preview_tmp()
        tab.deleteLater()
