"""Tests for SlideWindow theme/template menu handlers and close logic.

These drive the theme-editor/gallery/delete dialogs, the template submenu
population, the presentation-properties asset localisation, the no-tab
guards on the file handlers, and the dirty-tab close confirmation. Every
modal is stubbed so the synchronous controller logic runs headlessly.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

from epy_slides import app as app_module
from epy_slides import templates, themes
from epy_slides.app import SlideWindow
from epy_slides.tab import MarkdownTab


@pytest.fixture(scope="session", autouse=True)
def _isolate_qsettings(tmp_path_factory):
    cfg = tmp_path_factory.mktemp("qsettings_menus")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(cfg)
    )
    return cfg


@pytest.fixture
def window(qapp):
    win = SlideWindow()
    yield win
    for i in range(win.tabs.count()):
        widget = win.tabs.widget(i)
        if isinstance(widget, MarkdownTab):
            widget.cleanup_preview_tmp()
    win.deleteLater()


# --------------------------------------------------------------- theme editor


def test_open_theme_editor_saves_and_selects(window, monkeypatch):
    from epy_slides import theme_editor_dialog as ted

    monkeypatch.setattr(
        ted.ThemeEditorDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        ted.ThemeEditorDialog, "epyson_payload", lambda self: {"id": "x"}
    )
    monkeypatch.setattr(
        ted.ThemeEditorDialog, "theme_name", lambda self: "My Theme"
    )
    monkeypatch.setattr(
        themes, "save_user_theme", lambda payload: "mytheme"
    )
    selected: dict = {}
    monkeypatch.setattr(
        window, "_refresh_themes",
        lambda select_id=None: selected.update(id=select_id),
    )
    window._open_theme_editor()
    assert selected["id"] == "mytheme"


def test_open_theme_editor_cancelled_is_noop(window, monkeypatch):
    from epy_slides import theme_editor_dialog as ted

    monkeypatch.setattr(
        ted.ThemeEditorDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    saved = {"n": 0}
    monkeypatch.setattr(
        themes, "save_user_theme",
        lambda payload: saved.update(n=saved["n"] + 1),
    )
    window._open_theme_editor()
    assert saved["n"] == 0


def test_open_theme_editor_save_error_warns(window, monkeypatch):
    from epy_slides import theme_editor_dialog as ted

    monkeypatch.setattr(
        ted.ThemeEditorDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        ted.ThemeEditorDialog, "epyson_payload", lambda self: {}
    )

    def boom(payload):
        raise OSError("disk full")

    monkeypatch.setattr(themes, "save_user_theme", boom)
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._open_theme_editor()
    assert warned["n"] == 1


def test_edit_current_theme_clones_builtin(window, monkeypatch):
    captured: dict = {}
    monkeypatch.setattr(
        window, "_open_theme_editor",
        lambda edit_id=None: captured.update(edit_id=edit_id),
    )
    # The active theme is a builtin → edit_id stays None (clone path).
    window._edit_current_theme()
    assert captured["edit_id"] is None


# --------------------------------------------------------------- theme gallery


def test_open_theme_gallery_applies_selection(window, monkeypatch):
    from epy_slides import theme_gallery_dialog as tgd

    monkeypatch.setattr(
        tgd.ThemeGalleryDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        tgd.ThemeGalleryDialog, "selected_theme_id", lambda self: "minimal"
    )
    window._open_theme_gallery()
    assert window._current_theme.id == "minimal"


def test_open_theme_gallery_cancelled_keeps_theme(window, monkeypatch):
    from epy_slides import theme_gallery_dialog as tgd

    before = window._current_theme.id
    monkeypatch.setattr(
        tgd.ThemeGalleryDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    window._open_theme_gallery()
    assert window._current_theme.id == before


# --------------------------------------------------------------- delete theme


def test_delete_custom_theme_no_customs_informs(window, monkeypatch):
    monkeypatch.setattr(themes, "user_theme_ids", lambda: set())
    informed = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "information",
        staticmethod(lambda *a, **k: informed.update(n=informed["n"] + 1)),
    )
    window._delete_custom_theme()
    assert informed["n"] == 1


def test_delete_custom_theme_confirmed(window, monkeypatch):
    # Stub a single custom theme and confirm deletion.
    monkeypatch.setattr(themes, "user_theme_ids", lambda: {"custom1"})

    class _T:
        display_name = "Custom One"

    monkeypatch.setattr(themes, "THEMES", {"custom1": _T()})
    monkeypatch.setattr(
        QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("Custom One", True)),
    )
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Yes),
    )
    deleted: dict = {}
    monkeypatch.setattr(
        themes, "delete_user_theme",
        lambda tid: deleted.update(id=tid),
    )
    monkeypatch.setattr(window, "_refresh_themes", lambda select_id=None: None)
    window._delete_custom_theme()
    assert deleted["id"] == "custom1"


def test_delete_custom_theme_cancel_picker_is_noop(window, monkeypatch):
    monkeypatch.setattr(themes, "user_theme_ids", lambda: {"custom1"})

    class _T:
        display_name = "Custom One"

    monkeypatch.setattr(themes, "THEMES", {"custom1": _T()})
    monkeypatch.setattr(
        QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("", False)),
    )
    deleted = {"n": 0}
    monkeypatch.setattr(
        themes, "delete_user_theme",
        lambda tid: deleted.update(n=deleted["n"] + 1),
    )
    window._delete_custom_theme()
    assert deleted["n"] == 0


def test_delete_custom_theme_decline_confirm_is_noop(window, monkeypatch):
    monkeypatch.setattr(themes, "user_theme_ids", lambda: {"custom1"})

    class _T:
        display_name = "Custom One"

    monkeypatch.setattr(themes, "THEMES", {"custom1": _T()})
    monkeypatch.setattr(
        QInputDialog, "getItem",
        staticmethod(lambda *a, **k: ("Custom One", True)),
    )
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.No),
    )
    deleted = {"n": 0}
    monkeypatch.setattr(
        themes, "delete_user_theme",
        lambda tid: deleted.update(n=deleted["n"] + 1),
    )
    window._delete_custom_theme()
    assert deleted["n"] == 0


# --------------------------------------------------------------- about


def test_show_about_execs_dialog(window, monkeypatch):
    from epy_slides import about_dialog

    execed = {"n": 0}
    monkeypatch.setattr(
        about_dialog.AboutDialog, "exec",
        lambda self: execed.update(n=execed["n"] + 1),
    )
    window._show_about()
    assert execed["n"] == 1


# ------------------------------------------------------------- templates menu


def test_populate_apply_template_menu_empty(window, monkeypatch):
    monkeypatch.setattr(templates, "list_templates", lambda: [])
    window._populate_apply_template_menu()
    # A disabled placeholder action is added when there are no templates.
    actions = window.apply_template_menu.actions()
    assert len(actions) == 1
    assert not actions[0].isEnabled()


def test_populate_apply_template_menu_lists_names(window, monkeypatch):
    monkeypatch.setattr(
        templates, "list_templates", lambda: ["A", "B"]
    )
    window._populate_apply_template_menu()
    texts = [a.text() for a in window.apply_template_menu.actions()]
    assert texts == ["A", "B"]


def test_populate_delete_template_menu_empty(window, monkeypatch):
    monkeypatch.setattr(templates, "list_templates", lambda: [])
    window._populate_delete_template_menu()
    actions = window.delete_template_menu.actions()
    assert len(actions) == 1
    assert not actions[0].isEnabled()


def test_populate_delete_template_menu_lists_names(window, monkeypatch):
    monkeypatch.setattr(
        templates, "list_templates", lambda: ["One"]
    )
    window._populate_delete_template_menu()
    texts = [a.text() for a in window.delete_template_menu.actions()]
    assert texts == ["One"]


def test_save_template_reports_error(window, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("Name", True)),
    )

    def boom(name, data, *a, **k):
        raise OSError("cannot write template")

    monkeypatch.setattr(templates, "save_template", boom)
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._current_tab().set_initial_text("## A\n")
    window._save_template()
    assert warned["n"] == 1


def test_apply_template_without_tab_returns(window, monkeypatch):
    monkeypatch.setattr(
        templates, "load_template", lambda name: {"theme": "minimal"}
    )
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    # No tab → applies theme then returns before touching front matter.
    window._apply_template("whatever")
    assert window._current_theme.id == "minimal"


# ------------------------------------------------- presentation props guard


def test_edit_properties_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._edit_properties()  # must not raise


def test_edit_properties_localizes_logo_asset(window, tmp_path, monkeypatch):
    # An accepted properties dialog that returns a logo path triggers the
    # asset-localisation copy into figures/.
    deck = tmp_path / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    window.open_path(deck)
    logo = tmp_path / "brand.png"
    logo.write_bytes(b"\x89PNG\r\n")

    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    from epy_slides import presentation_properties_dialog as ppd

    monkeypatch.setattr(
        ppd.PresentationPropertiesDialog, "updates",
        lambda self: [("logo", str(logo), False)],
    )
    window._edit_properties()
    assert "figures/brand.png" in window._current_tab().text()
    assert (tmp_path / "figures" / "brand.png").is_file()


# ------------------------------------------------- export guards (no tab)


def test_export_html_no_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    window._export_html()  # must not raise


# --------------------------------------------------------------- open manual


def test_open_manual_unavailable_warns(window, monkeypatch):
    monkeypatch.setattr(
        app_module, "_load_manual_text",
        lambda filename: (_ for _ in ()).throw(FileNotFoundError("x")),
    )
    warned = {"n": 0}
    monkeypatch.setattr(
        app_module.QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    window._open_manual("ghost.md")
    assert warned["n"] == 1


def test_open_manual_loads_into_tab(window, monkeypatch):
    monkeypatch.setattr(
        app_module, "_load_manual_text", lambda filename: "## Manual\n"
    )
    before = window.tabs.count()
    window._open_manual("welcome.md")
    assert window.tabs.count() == before + 1


# --------------------------------------------------------------- close logic


def test_confirm_close_clean_tab_returns_true(window):
    tab = window._current_tab()
    tab.set_initial_text("clean\n")  # resets dirty
    assert window._confirm_close(tab) is True


def test_confirm_close_dirty_save_choice(window, tmp_path, monkeypatch):
    deck = tmp_path / "d.md"
    deck.write_text("disk\n", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    tab.editor.setPlainText("edited")
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Save),
    )
    assert window._confirm_close(tab) is True
    assert deck.read_text(encoding="utf-8") == "edited"


def test_confirm_close_dirty_discard_choice(window):
    tab = window._current_tab()
    tab.set_initial_text("base\n")
    tab.editor.setPlainText("dirty edit")

    import epy_slides.app as appmod

    orig = appmod.QMessageBox.question
    try:
        appmod.QMessageBox.question = staticmethod(
            lambda *a, **k: QMessageBox.StandardButton.Discard
        )
        assert window._confirm_close(tab) is True
    finally:
        appmod.QMessageBox.question = orig


def test_close_event_aborts_when_cancelled(window, monkeypatch):
    from PySide6.QtGui import QCloseEvent

    tab = window._current_tab()
    tab.set_initial_text("base\n")
    tab.editor.setPlainText("dirty")
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    event = QCloseEvent()
    window.closeEvent(event)
    assert not event.isAccepted()


def test_close_event_accepts_when_clean(window):
    from PySide6.QtGui import QCloseEvent

    window._current_tab().set_initial_text("clean\n")
    event = QCloseEvent()
    window.closeEvent(event)
    assert event.isAccepted()


def test_close_current_tab_via_shortcut(window):
    window._current_tab().set_initial_text("clean\n")
    window._close_current_tab()  # must not raise; reopens welcome if empty
    assert window.tabs.count() >= 1


def test_close_tab_at_non_markdown_index_is_noop(window):
    # Index out of range yields a non-MarkdownTab widget (None) → no-op.
    window._close_tab_at(999)
    assert window.tabs.count() >= 1
