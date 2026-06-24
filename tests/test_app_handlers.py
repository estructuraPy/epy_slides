"""Controller tests for SlideWindow dialog-driven handlers.

These exercise the synchronous menu handlers that normally pop a modal
(template save/delete, presentation properties, citation/bibliography
insertion, open/reload). Each modal is stubbed so the handler runs to
completion headlessly and its real front-matter / file side effects are
asserted. The asynchronous preview/PDF render paths are not driven here.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QDialog,
    QInputDialog,
    QMessageBox,
)

from epy_slides import app as app_module
from epy_slides import templates
from epy_slides.app import SlideWindow
from epy_slides.bib import BibEntryDraft
from epy_slides.tab import MarkdownTab


@pytest.fixture(scope="session", autouse=True)
def _isolate_qsettings(tmp_path_factory):
    """Redirect INI QSettings to a temp dir for the whole session."""
    cfg = tmp_path_factory.mktemp("qsettings_handlers")
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


# --------------------------------------------------------------- templates


def test_save_template_writes_file(window, tmp_path, monkeypatch):
    # _save_template imports QInputDialog locally, so patch the real class.
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: ("HouseStyle", True)),
    )
    monkeypatch.setattr(
        templates, "save_template",
        lambda name, data, *a, **k: captured.update(name=name, data=data),
    )
    captured: dict = {}
    tab = window._current_tab()
    tab.set_initial_text("---\nfooter: Conf\n---\n\n## A\n")
    window._save_template()
    assert captured["name"] == "HouseStyle"
    assert captured["data"]["theme"] == window._current_theme.id
    assert captured["data"]["footer"] == "Conf"


def test_save_template_cancelled_is_noop(window, monkeypatch):
    monkeypatch.setattr(
        QInputDialog,
        "getText",
        staticmethod(lambda *a, **k: ("", False)),
    )
    called = {"saved": False}
    monkeypatch.setattr(
        templates, "save_template",
        lambda *a, **k: called.update(saved=True),
    )
    window._save_template()
    assert called["saved"] is False


def test_apply_template_missing_warns_and_returns(window, monkeypatch):
    monkeypatch.setattr(
        templates, "load_template",
        lambda name: (_ for _ in ()).throw(FileNotFoundError("nope")),
    )
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._apply_template("ghost")
    assert warned["n"] == 1


def test_delete_template_confirmed(window, monkeypatch):
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    deleted = {"name": None}
    monkeypatch.setattr(
        templates, "delete_template",
        lambda name, *a, **k: deleted.update(name=name),
    )
    window._delete_template("Old")
    assert deleted["name"] == "Old"


def test_delete_template_declined_is_noop(window, monkeypatch):
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    called = {"deleted": False}
    monkeypatch.setattr(
        templates, "delete_template",
        lambda *a, **k: called.update(deleted=True),
    )
    window._delete_template("Old")
    assert called["deleted"] is False


# ----------------------------------------------- presentation properties


def test_edit_properties_writes_front_matter(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")

    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )

    from epy_slides import presentation_properties_dialog as ppd

    monkeypatch.setattr(
        ppd.PresentationPropertiesDialog,
        "updates",
        lambda self: [("footer", "Page footer", False)],
    )
    window._edit_properties()
    assert "footer: Page footer" in tab.text()


def test_edit_properties_cancelled_is_noop(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    before = tab.text()
    window._edit_properties()
    assert tab.text() == before


# ----------------------------------------------- citations / bibliography


def test_insert_citation_without_entries_informs(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    informed = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "information",
        staticmethod(lambda *a, **k: informed.update(n=informed["n"] + 1)),
    )
    window._insert_citation()
    assert informed["n"] == 1


def test_insert_citation_inserts_key(window, tmp_path, monkeypatch):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{smith2020,\n  title = {T},\n  author = {Smith, J},\n"
        "  year = {2020},\n  journal = {J}\n}\n",
        encoding="utf-8",
    )
    deck = tmp_path / "deck.md"
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    window.open_path(deck)
    tab = window._current_tab()

    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    from epy_slides.snippets import Label
    from epy_slides.xref_dialog import CrossRefDialog

    monkeypatch.setattr(
        CrossRefDialog, "selected_label",
        lambda self: Label(kind="cite", name="smith2020"),
    )
    window._insert_citation()
    assert "[@smith2020]" in tab.text()


def test_insert_citation_cancelled_inserts_nothing(
    window, tmp_path, monkeypatch
):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{a2020, title={T}, author={X, Y}, year={2020}, "
        "journal={J}}\n",
        encoding="utf-8",
    )
    deck = tmp_path / "deck.md"
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    window.open_path(deck)
    before = window._current_tab().text()
    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    window._insert_citation()
    assert window._current_tab().text() == before


def test_insert_citation_accepted_without_label_is_noop(
    window, tmp_path, monkeypatch
):
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@article{a2020, title={T}, author={X, Y}, year={2020}, "
        "journal={J}}\n",
        encoding="utf-8",
    )
    deck = tmp_path / "deck.md"
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    window.open_path(deck)
    before = window._current_tab().text()
    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    from epy_slides.xref_dialog import CrossRefDialog

    monkeypatch.setattr(
        CrossRefDialog, "selected_label", lambda self: None
    )
    window._insert_citation()
    assert window._current_tab().text() == before


def test_insert_citation_no_tab_is_noop(window, monkeypatch):
    # Force a bib-bearing tab check, then no current tab on the second call.
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._insert_citation()  # must not raise


def test_new_bib_entry_cancelled_writes_nothing(
    window, tmp_path, monkeypatch
):
    bib = tmp_path / "refs.bib"
    bib.write_text("@misc{seed, title={Z}}\n", encoding="utf-8")
    deck = tmp_path / "deck.md"
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    window.open_path(deck)
    before = bib.read_text(encoding="utf-8")
    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    window._new_bib_entry()
    assert bib.read_text(encoding="utf-8") == before


def test_link_bibliography_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._link_bibliography()  # must not raise


def test_set_csl_style_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._set_csl_style("apa")  # must not raise


def test_link_bibliography_writes_front_matter(window, tmp_path, monkeypatch):
    bib = tmp_path / "library.bib"
    bib.write_text("@misc{x,\n  title = {Y}\n}\n", encoding="utf-8")
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    monkeypatch.setattr(
        app_module.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(bib), "")),
    )
    window._link_bibliography()
    assert "bibliography:" in tab.text()
    assert "library.bib" in tab.text()


def test_link_bibliography_cancelled_is_noop(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    monkeypatch.setattr(
        app_module.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    before = tab.text()
    window._link_bibliography()
    assert tab.text() == before


def test_new_bib_entry_without_bib_informs(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    informed = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "information",
        staticmethod(lambda *a, **k: informed.update(n=informed["n"] + 1)),
    )
    window._new_bib_entry()
    assert informed["n"] == 1


def test_new_bib_entry_appends_to_file(window, tmp_path, monkeypatch):
    bib = tmp_path / "refs.bib"
    bib.write_text("@misc{seed,\n  title = {Z}\n}\n", encoding="utf-8")
    deck = tmp_path / "deck.md"
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    window.open_path(deck)

    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    from epy_slides.bib_dialog import BibEntryDialog

    monkeypatch.setattr(
        BibEntryDialog, "build_draft",
        lambda self: BibEntryDraft(
            type="article", key="new2021", author="Doe, J",
            title="New", year="2021", journal="J",
        ),
    )
    window._new_bib_entry()
    text = bib.read_text(encoding="utf-8")
    assert "@article{new2021," in text


# --------------------------------------------------------------- open / reload


def test_open_dialog_loads_selected_files(window, tmp_path, monkeypatch):
    deck = tmp_path / "picked.md"
    deck.write_text("## Picked\n", encoding="utf-8")
    monkeypatch.setattr(
        app_module.QFileDialog, "getOpenFileNames",
        staticmethod(lambda *a, **k: ([str(deck)], "")),
    )
    window._open_dialog()
    titles = [
        window.tabs.widget(i).path
        for i in range(window.tabs.count())
        if isinstance(window.tabs.widget(i), MarkdownTab)
        and window.tabs.widget(i).path is not None
    ]
    assert deck.resolve() in titles


def test_reload_current_dirty_declined_keeps_buffer(
    window, tmp_path, monkeypatch
):
    deck = tmp_path / "deck.md"
    deck.write_text("on disk\n", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    tab.editor.setPlainText("edited in memory")
    assert tab.dirty is True
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    window._reload_current()
    # Declined → the in-memory edit is preserved (no reload from disk).
    assert tab.text() == "edited in memory"


def test_reload_current_dirty_confirmed_reloads(
    window, tmp_path, monkeypatch
):
    deck = tmp_path / "deck.md"
    deck.write_text("on disk\n", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    tab.editor.setPlainText("edited in memory")
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    window._reload_current()
    assert tab.text() == "on disk\n"
    assert tab.dirty is False


# --------------------------------------------------------------- CSL style


def test_set_csl_style_checks_action_and_writes(window):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    window._set_csl_style("nature")
    assert "citation-style: nature" in tab.text()
    assert window.csl_actions["nature"].isChecked()
