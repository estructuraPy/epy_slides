"""Tests for the SlideWindow main window and CLI entry helpers.

The window is built once per test against an isolated ``QSettings`` INI in a
temp dir, so theme/language persistence never touches the real user config.
The asynchronous preview/PDF paths are not driven here; we exercise the
synchronous controller logic: tab management, file open/save, theme and
language switching, template/citation/CSL front-matter edits, drag-and-drop
and the argument parser / CLI dispatch.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QMimeData, QPointF, QSettings, Qt, QUrl
from PySide6.QtGui import QDropEvent

from epy_slides import app as app_module
from epy_slides import themes
from epy_slides.app import (
    SUPPORTED_EXTENSIONS,
    SlideWindow,
    _build_parser,
    _ensure_utf8_streams,
    _load_manual_text,
    _load_welcome,
    main,
)
from epy_slides.tab import MarkdownTab


@pytest.fixture(scope="session", autouse=True)
def _isolate_qsettings(tmp_path_factory):
    """Redirect INI-format QSettings for the whole session to a temp dir."""
    cfg = tmp_path_factory.mktemp("qsettings")
    QSettings.setDefaultFormat(QSettings.Format.IniFormat)
    QSettings.setPath(
        QSettings.Format.IniFormat,
        QSettings.Scope.UserScope,
        str(cfg),
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


# --------------------------------------------------------------- module-level


def test_load_welcome_returns_deck():
    text = _load_welcome()
    assert "---" in text
    assert isinstance(text, str)


def test_load_manual_text_resolves_placeholders():
    text = _load_manual_text("welcome.md")
    # The logo placeholder must be replaced (no raw token remains).
    assert "__EPY_LOGO__" not in text


def test_supported_extensions():
    assert {".md", ".markdown", ".qmd"} == SUPPORTED_EXTENSIONS


def test_load_manual_text_spanish_variant_resolves():
    # The Spanish manual stem ends with ``_es``; its screenshot resolution
    # prefers the ``*_es.png`` variants and still drops the logo token.
    text = _load_manual_text("welcome_es.md")
    assert "__EPY_LOGO__" not in text
    assert isinstance(text, str)


def test_load_manual_text_drops_missing_image(monkeypatch):
    # When a bundled image cannot be resolved, its placeholder (and any
    # image markdown using it) is stripped so Pandoc never aborts.
    import importlib.resources as ir

    real_files = ir.files

    class _AlwaysMissing:
        def __init__(self, real):
            self._real = real

        def joinpath(self, *parts):
            return _AlwaysMissing(self._real.joinpath(*parts))

        def read_text(self, *a, **k):
            # The manual body itself must still load.
            return self._real.read_text(*a, **k)

        def is_file(self):
            return False

    def fake_files(package):
        node = real_files(package)
        if package == "epy_slides.assets":
            return _AlwaysMissing(node)
        return node

    monkeypatch.setattr(
        app_module.importlib.resources, "files", fake_files
    )
    text = _load_manual_text("welcome.md")
    assert "__EPY_LOGO__" not in text
    assert "__SHOT_EDITOR__" not in text


def test_load_welcome_falls_back_on_error(monkeypatch):
    def boom(_filename="welcome.md"):
        raise FileNotFoundError("no manual")

    monkeypatch.setattr(app_module, "_load_manual_text", boom)
    text = _load_welcome()
    assert "Getting started" in text


# --------------------------------------------------------------- construction


def test_window_builds_with_welcome_tab(window):
    assert window.tabs.count() == 1
    assert isinstance(window._current_tab(), MarkdownTab)
    # The toolbar dropdowns and theme actions were created.
    assert window._toolbar_buttons
    assert window.theme_actions
    assert window.lang_actions == {"en": window.lang_actions["en"],
                                   "es": window.lang_actions["es"]}


def test_current_theme_is_a_known_theme(window):
    assert window._current_theme.id in themes.THEMES


# ------------------------------------------------------------- tab management


def test_new_tab_adds_empty_tab(window):
    before = window.tabs.count()
    tab = window._new_tab()
    assert window.tabs.count() == before + 1
    assert tab.text() == ""
    assert window._current_tab() is tab


def test_open_path_loads_file(window, tmp_path):
    deck = tmp_path / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    assert tab is not None
    assert tab.text() == "## Slide\n"
    assert tab.path == deck.resolve()


def test_open_path_focuses_existing_tab(window, tmp_path):
    deck = tmp_path / "deck.md"
    deck.write_text("## A\n", encoding="utf-8")
    window.open_path(deck)
    count_after_first = window.tabs.count()
    window.open_path(deck)  # same path → must not add a new tab
    assert window.tabs.count() == count_after_first


def test_open_path_non_file_is_handled(window, tmp_path, monkeypatch):
    missing = tmp_path / "nope.md"
    # open_path warns via a modal QMessageBox for a non-file; stub it so
    # the static exec() does not block forever under the offscreen platform.
    monkeypatch.setattr(
        app_module.QMessageBox,
        "warning",
        staticmethod(lambda *a, **k: None),
    )
    # Must not raise even though the path is not a file.
    window.open_path(missing)


def test_close_tab_reopens_welcome_when_empty(window):
    # Closing the only (clean) tab should reopen a fresh welcome tab.
    assert window.tabs.count() == 1
    window._close_tab_at(0)
    assert window.tabs.count() == 1


def test_update_window_title_reflects_tab(window, tmp_path):
    deck = tmp_path / "named.md"
    deck.write_text("x", encoding="utf-8")
    window.open_path(deck)
    window._update_window_title()
    assert "named.md" in window.windowTitle()


# --------------------------------------------------------------- save / reload


def test_save_current_without_path_uses_save_as(window, tmp_path, monkeypatch):
    tab = window._new_tab()
    tab.editor.setPlainText("payload")
    target = tmp_path / "saved.md"
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(target), "")),
    )
    assert window._save_current() is True
    assert target.read_text(encoding="utf-8") == "payload"
    assert tab.path == target


def test_save_current_as_cancelled(window, monkeypatch):
    window._new_tab()
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    assert window._save_current_as() is False


def test_save_current_with_existing_path(window, tmp_path):
    deck = tmp_path / "deck.md"
    deck.write_text("old", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    tab.editor.setPlainText("new content")
    assert window._save_current() is True
    assert deck.read_text(encoding="utf-8") == "new content"


def test_reload_current_no_path_is_noop(window):
    window._new_tab()
    window._reload_current()  # untitled → no-op, must not raise


# --------------------------------------------------------------- themes


def test_apply_theme_switches_current(window):
    window._apply_theme("minimal")
    assert window._current_theme.id == "minimal"
    # The matching radio action is ticked.
    assert window.theme_actions["minimal"].isChecked()


def test_apply_theme_persists_to_settings(window):
    window._apply_theme("scientific", persist=True)
    saved = str(window._settings.value("theme"))
    assert saved == "scientific"


def test_refresh_themes_keeps_default(window):
    window._refresh_themes()
    assert themes.DEFAULT_THEME_ID in window.theme_actions


# --------------------------------------------------------------- language


def test_set_language_updates_state_and_settings(window):
    from epy_slides import _i18n as i18n

    try:
        window._set_language("es")
        assert i18n.current_language() == "es"
        assert str(window._settings.value("language")) == "es"
        assert window.lang_actions["es"].isChecked()
    finally:
        window._set_language("en")


def test_window_applies_saved_spanish_language_on_build(qapp):
    # A persisted non-English language must be applied as the window builds
    # (the construction-time set_language branch).
    from epy_slides import _i18n as i18n

    settings = QSettings("ANM Ingeniería", "epy_slides")
    settings.setValue("language", "es")
    settings.sync()
    try:
        win = SlideWindow()
        try:
            assert i18n.current_language() == "es"
        finally:
            for i in range(win.tabs.count()):
                w = win.tabs.widget(i)
                if isinstance(w, MarkdownTab):
                    w.cleanup_preview_tmp()
            win.deleteLater()
    finally:
        settings.setValue("language", "en")
        settings.sync()
        i18n.set_language("en")


def test_retranslate_ui_runs(window):

    try:
        window._set_language("es")
        window._retranslate_ui()
        # A captured File action should now show Spanish text.
        assert window.act_open.text() == "Abrir..."
    finally:
        window._set_language("en")


# --------------------------------------------------------------- templates


def test_apply_template_sets_theme_and_front_matter(window, monkeypatch):
    from epy_slides import templates

    monkeypatch.setattr(
        templates,
        "load_template",
        lambda name: {"theme": "minimal", "footer": "Confidential"},
    )
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    window._apply_template("whatever")
    assert window._current_theme.id == "minimal"
    assert "footer: Confidential" in tab.text()


def test_set_csl_style_writes_front_matter(window):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    window._set_csl_style("apa")
    assert "citation-style: apa" in tab.text()
    assert window.csl_actions["apa"].isChecked()


# --------------------------------------------------------------- helpers


def test_replace_buffer_preserves_text(window):
    tab = window._new_tab()
    tab.editor.setPlainText("before")
    SlideWindow._replace_buffer(tab, "after")
    assert tab.text() == "after"


def test_localize_asset_relative_unchanged(window):
    tab = window._new_tab()
    assert SlideWindow._localize_asset(tab, "figures/logo.png") == (
        "figures/logo.png"
    )


def test_localize_asset_copies_into_figures(window, tmp_path):
    deck = tmp_path / "deck.md"
    deck.write_text("x", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    logo = tmp_path / "external_logo.png"
    logo.write_bytes(b"\x89PNG\r\n")
    result = SlideWindow._localize_asset(tab, str(logo))
    assert result == "figures/external_logo.png"
    assert (tmp_path / "figures" / "external_logo.png").is_file()


def test_on_active_tab_forwards(window):
    tab = window._current_tab()
    tab.set_initial_text("Title")
    window._on_active_tab("set_heading_level", 2)
    assert tab.text().startswith("## Title")


# --------------------------------------------------------------- export html


def test_export_html_writes_file(window, tmp_path, monkeypatch):
    deck = tmp_path / "deck.md"
    deck.write_text("## A\n\n- one\n", encoding="utf-8")
    window.open_path(deck)
    out = tmp_path / "deck.html"
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: (str(out), "")),
    )
    window._export_html()
    assert out.is_file()
    assert '<div class="reveal">' in out.read_text(encoding="utf-8")


def test_export_html_cancelled_writes_nothing(window, tmp_path, monkeypatch):
    window._new_tab()
    monkeypatch.setattr(
        app_module.QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    window._export_html()  # cancelled → no exception


# --------------------------------------------------------------- drag & drop


def test_drop_event_opens_supported_files(window, tmp_path):
    deck = tmp_path / "dropped.md"
    deck.write_text("## Dropped\n", encoding="utf-8")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(deck))])
    event = QDropEvent(
        QPointF(0, 0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dropEvent(event)
    paths = [
        window.tabs.widget(i).path
        for i in range(window.tabs.count())
        if isinstance(window.tabs.widget(i), MarkdownTab)
        and window.tabs.widget(i).path is not None
    ]
    assert deck.resolve() in paths


# --------------------------------------------------------------- CLI / parser


def test_build_parser_defaults():
    parser = _build_parser()
    args = parser.parse_args([])
    assert args.files == []
    assert args.register is False
    assert args.unregister is False
    assert args.set_default is False


def test_build_parser_flags():
    parser = _build_parser()
    args = parser.parse_args(["a.md", "--register", "--as-default"])
    assert args.files == ["a.md"]
    assert args.register is True
    assert args.as_default is True


def test_ensure_utf8_streams_runs():
    _ensure_utf8_streams()  # must not raise


def test_ensure_utf8_streams_handles_none_and_missing_reconfigure(
    monkeypatch,
):
    import sys

    class _NoReconfigure:
        # A stream object without a ``reconfigure`` attribute.
        pass

    # stdout is None (skipped), stderr lacks reconfigure (also skipped).
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", _NoReconfigure())
    _ensure_utf8_streams()  # must not raise


def test_on_active_tab_without_tab_is_noop(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    # No tab → the forwarded action is silently dropped.
    window._on_active_tab("set_heading_level", 2)


def test_main_dispatches_unregister(monkeypatch):
    called: list[str] = []
    monkeypatch.setattr(
        app_module, "_run_unregister", lambda: called.append("u") or 0
    )
    assert main(["--unregister"]) == 0
    assert called == ["u"]


def test_main_dispatches_register(monkeypatch):
    seen: dict[str, bool] = {}
    def fake_register(make_default):
        seen["d"] = make_default
        return 0

    monkeypatch.setattr(app_module, "_run_register", fake_register)
    assert main(["--register", "--as-default"]) == 0
    assert seen["d"] is True


def test_main_dispatches_set_default(monkeypatch):
    monkeypatch.setattr(app_module, "_run_set_default", lambda: 7)
    assert main(["--set-default"]) == 7


def test_main_dispatches_gui(monkeypatch):
    monkeypatch.setattr(app_module, "_run_gui", lambda files: 0)
    assert main([]) == 0


# ----------------------------------------------- CLI registration helpers


def test_run_register_reports_changes(monkeypatch, capsys):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(
        winreg_assoc, "register", lambda make_default: ["did A", "did B"]
    )
    monkeypatch.setattr(
        winreg_assoc, "open_default_apps_settings", lambda: True
    )
    assert app_module._run_register(make_default=True) == 0
    out = capsys.readouterr().out
    assert "did A" in out and "did B" in out


def test_run_register_handles_runtime_error(monkeypatch, capsys):
    from epy_slides import winreg_assoc

    def boom(make_default):
        raise RuntimeError("not on windows")

    monkeypatch.setattr(winreg_assoc, "register", boom)
    assert app_module._run_register(make_default=False) == 2
    assert "not on windows" in capsys.readouterr().err


def test_run_unregister_nothing_to_remove(monkeypatch, capsys):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "unregister", lambda: [])
    assert app_module._run_unregister() == 0
    assert "Nothing to remove" in capsys.readouterr().out


def test_run_unregister_reports_changes(monkeypatch, capsys):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "unregister", lambda: ["removed X"])
    assert app_module._run_unregister() == 0
    assert "removed X" in capsys.readouterr().out


def test_run_unregister_handles_runtime_error(monkeypatch):
    from epy_slides import winreg_assoc

    def boom():
        raise RuntimeError("nope")

    monkeypatch.setattr(winreg_assoc, "unregister", boom)
    assert app_module._run_unregister() == 2


def test_run_set_default_success(monkeypatch):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(
        winreg_assoc, "open_default_apps_settings", lambda: True
    )
    assert app_module._run_set_default() == 0


def test_run_set_default_failure(monkeypatch, capsys):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(
        winreg_assoc, "open_default_apps_settings", lambda: False
    )
    assert app_module._run_set_default() == 2
    assert "Could not open Settings" in capsys.readouterr().err


# --------------------------------------------------------------- drag enter


def test_drag_enter_accepts_urls(window):
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QDragEnterEvent

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile("x.md")])
    event = QDragEnterEvent(
        QPoint(0, 0),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    window.dragEnterEvent(event)
    assert event.isAccepted()
