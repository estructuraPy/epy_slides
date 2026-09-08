"""The second rendering option, as a person meets it.

An action that exists, is offered when the engine can be reached, and
runs the render off the interface thread. The bridge and the dialog can
both be right while nothing in the window ever calls them, which is the
shape this suite has been finding all week.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QDialog

from epy_slides._ui.tab import MarkdownTab
from epy_slides.app import SlideWindow


@pytest.fixture
def window(qapp):
    win = SlideWindow()
    yield win
    for index in range(win.tabs.count()):
        widget = win.tabs.widget(index)
        if isinstance(widget, MarkdownTab):
            widget.cleanup_preview_tmp()
    win.deleteLater()


def test_the_action_exists_and_is_in_the_export_menu(window) -> None:
    assert hasattr(window, "act_docs_export")
    titles = [action.text() for action in window.export_menu.actions()]
    assert "Export via epy_docs..." in titles


def test_it_sits_after_the_deck_exports(window) -> None:
    # ePy Docs makes documents, not decks: what it produces is the
    # handout, not the presentation. A separator says that without a
    # sentence.
    actions = list(window.export_menu.actions())
    docs = next(
        index
        for index, action in enumerate(actions)
        if action.text() == "Export via epy_docs..."
    )
    assert actions[docs - 1].isSeparator()


def test_it_is_offered_when_the_engine_can_be_reached(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Enablement is decided when the window is built, which is when ePy
    # Studio's hint is already in the environment.
    from epy_slides import app as app_module

    monkeypatch.setattr(app_module, "docs_available", lambda: True)
    win = SlideWindow()
    try:
        assert win.act_docs_export.isEnabled()
    finally:
        win.deleteLater()


def test_it_is_greyed_with_a_reason_when_it_cannot(
    qapp, monkeypatch: pytest.MonkeyPatch
) -> None:
    from epy_slides import app as app_module

    monkeypatch.setattr(app_module, "docs_available", lambda: False)
    win = SlideWindow()
    try:
        assert not win.act_docs_export.isEnabled()
        assert "epy-docs" in win.act_docs_export.toolTip()
    finally:
        win.deleteLater()


def test_an_unsaved_deck_is_asked_about_before_anything_opens(
    window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # The engine reads a FILE, so an unsaved buffer has nothing to give
    # it. Saving somebody's deck because they opened an export dialog is
    # not the export they asked for.
    from PySide6.QtWidgets import QMessageBox

    from epy_slides import app as app_module

    asked: list[str] = []

    def _decline(*args: object, **kwargs: object) -> object:
        asked.append("asked")
        return QMessageBox.StandardButton.Cancel

    monkeypatch.setattr(app_module.QMessageBox, "question", _decline)
    opened: list[str] = []
    from epy_slides._ui import docs_export_dialog as ded

    monkeypatch.setattr(
        ded.DocsExportDialog, "exec",
        lambda self: opened.append("opened") or QDialog.DialogCode.Rejected,
    )
    window._export_via_docs()
    assert asked == ["asked"]
    assert opened == []


def test_the_render_runs_off_the_interface_thread(
    window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A render may take minutes and may start a child interpreter.
    # Doing it on the GUI thread freezes the window for the whole of it.
    from epy_slides._ui import docs_export_dialog as ded

    source = tmp_path / "charla.md"
    source.write_text("# Titulo\n\nUn parrafo.\n", encoding="utf-8")
    tab = window._current_tab()
    assert tab is not None
    # Both are read-only properties on the tab, so the type is what
    # answers: the point here is the thread, not how a tab is loaded.
    monkeypatch.setattr(type(tab), "path", property(lambda self: source))
    monkeypatch.setattr(type(tab), "dirty", property(lambda self: False))

    monkeypatch.setattr(
        ded.DocsExportDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    started: list[str] = []
    monkeypatch.setattr(
        ded._RenderWorker, "start", lambda self: started.append("started")
    )
    window._export_via_docs()
    assert started == ["started"]
    assert isinstance(window._docs_worker, ded._RenderWorker)


def test_the_engines_message_is_the_one_shown(
    window, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The library's own diagnosis is what a reader can act on; a generic
    # "export failed" sends them to the wrong place.
    from epy_slides import app as app_module

    shown: list[str] = []
    monkeypatch.setattr(
        app_module.QMessageBox,
        "critical",
        lambda *args, **kwargs: shown.append(args[2]),
    )
    window._on_docs_done_err("Quarto is not installed")
    assert shown
    assert "Quarto is not installed" in shown[0]


def test_success_says_where_the_documents_went(
    window, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    window._on_docs_done_ok(str(tmp_path / "out"))
    assert "out" in window.statusBar().currentMessage()
