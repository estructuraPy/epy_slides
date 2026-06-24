"""Coverage closers for the few residual branches in ``app.py``.

Each test here drives one specific guard or fallback that the broader
behavioural suites do not happen to reach: asset-resolution exception
handlers in ``_load_manual_text``, the localized theme-refresh path, the
``_apply_theme`` repaint triggered from presentation properties, the
suffix-defaulting on HTML export / Save As, and the early ``return``
guards in tab-title refresh, save, and tab-close handlers. Every Qt modal
and asset boundary is stubbed; nothing renders.
"""

from __future__ import annotations

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QDialog, QMessageBox

from epy_slides import _i18n as i18n
from epy_slides import app as app_module
from epy_slides import themes
from epy_slides.app import SlideWindow
from epy_slides.tab import MarkdownTab


@pytest.fixture(scope="session", autouse=True)
def _isolate_qsettings(tmp_path_factory):
    """Redirect INI QSettings to a temp dir for the whole session."""
    cfg = tmp_path_factory.mktemp("qsettings_cov100")
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


# ------------------------------------------------- _load_manual_text guards


class _RaisingResource:
    """A Traversable-like stub whose probes raise ``OSError``."""

    def joinpath(self, *_parts):
        return self

    def is_file(self):
        raise OSError("simulated probe failure")

    def read_text(self, *_args, **_kwargs):
        # The Spanish manual body still needs to load before asset probing.
        # Include a screenshot placeholder so the ``is_es`` branch (a
        # screenshot subdir) is exercised alongside the logo.
        return (
            "## Manual\n\n"
            "![logo](__EPY_LOGO__)\n\n"
            "![editor](__SHOT_EDITOR__)\n"
        )


def test_load_manual_text_swallows_es_probe_oserror(monkeypatch):
    # A ``*_es`` manual whose screenshot ``.is_file()`` raises OSError must
    # fall through the inner try/except and still return cleaned text.
    monkeypatch.setattr(
        app_module.importlib.resources,
        "files",
        lambda _pkg: _RaisingResource(),
    )
    out = app_module._load_manual_text("welcome_es.md")
    # The logo placeholder could not resolve (probe raised) so the image
    # was stripped rather than left dangling.
    assert "__EPY_LOGO__" not in out
    assert "Manual" in out


# ---------------------------------------------------- _refresh_themes (i18n)


def test_refresh_themes_retranslates_when_localized(window, monkeypatch):
    # Force a non-English current language so _refresh_themes calls
    # _retranslate_ui, and pass select_id so _apply_theme runs too.
    monkeypatch.setattr(i18n, "current_language", lambda: "es")
    retranslated = {"n": 0}
    monkeypatch.setattr(
        window,
        "_retranslate_ui",
        lambda: retranslated.update(n=retranslated["n"] + 1),
    )
    applied = {"id": None}
    monkeypatch.setattr(
        window, "_apply_theme", lambda tid, **k: applied.update(id=tid)
    )
    default_id = window._current_theme.id
    window._refresh_themes(select_id=default_id)
    assert retranslated["n"] == 1
    assert applied["id"] == default_id


# -------------------------------------- _edit_properties → _apply_theme path


def test_edit_properties_theme_change_repaints(window, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    current = window._current_theme.id
    target = next(tid for tid in themes.THEMES if tid != current)

    monkeypatch.setattr(
        app_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    from epy_slides import presentation_properties_dialog as ppd

    monkeypatch.setattr(
        ppd.PresentationPropertiesDialog,
        "updates",
        lambda self: [("theme", target, False)],
    )
    applied = {"id": None}
    monkeypatch.setattr(
        window, "_apply_theme", lambda tid, **k: applied.update(id=tid)
    )
    window._edit_properties()
    assert applied["id"] == target


# ------------------------------------------------ export / save suffix default


def test_export_html_adds_default_suffix(window, tmp_path, monkeypatch):
    # A target with no extension must gain ``.html`` before the (real, but
    # pure-string) reveal.js export writes the file. No Chromium involved.
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    bare = tmp_path / "deck_no_ext"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(bare), "")),
    )
    window._export_html()
    assert (tmp_path / "deck_no_ext.html").is_file()


def test_save_current_as_adds_default_suffix(window, tmp_path, monkeypatch):
    tab = window._current_tab()
    tab.set_initial_text("## Slide\n")
    bare = tmp_path / "untitled_no_ext"
    monkeypatch.setattr(
        app_module.QFileDialog, "getSaveFileName",
        staticmethod(lambda *a, **k: (str(bare), "")),
    )
    saved = {"target": None}
    monkeypatch.setattr(
        type(tab), "save_as",
        lambda self, target: saved.update(target=target),
    )
    assert window._save_current_as() is True
    assert str(saved["target"]).endswith(".md")


# ------------------------------------------------------- early-return guards


def test_refresh_tab_title_unknown_tab_returns(window):
    # A MarkdownTab not in the tab widget → indexOf < 0 → early return.
    orphan = MarkdownTab()
    try:
        window._refresh_tab_title(orphan)  # must not raise
    finally:
        orphan.cleanup_preview_tmp()
        orphan.deleteLater()


def test_save_current_without_tab_returns_false(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    assert window._save_current() is False


def test_save_current_as_without_tab_returns_false(window, monkeypatch):
    monkeypatch.setattr(window, "_current_tab", lambda: None)
    assert window._save_current_as() is False


def test_close_tab_at_declined_keeps_tab(window, tmp_path, monkeypatch):
    deck = tmp_path / "deck.md"
    deck.write_text("on disk\n", encoding="utf-8")
    window.open_path(deck)
    tab = window._current_tab()
    tab.editor.setPlainText("dirty edit")
    index = window.tabs.indexOf(tab)
    before = window.tabs.count()
    monkeypatch.setattr(
        app_module.QMessageBox, "question",
        staticmethod(lambda *a, **k: QMessageBox.StandardButton.Cancel),
    )
    window._close_tab_at(index)
    # Declined → tab is still present.
    assert window.tabs.count() == before


# ------------------------------------------------- _open_design_block_picker


def test_open_design_block_picker_accepted_inserts_block(window, monkeypatch):
    # Accepted dialog with a known kind → _on_active_tab is called with
    # ("insert_design_block", kind); the lazy import inside the handler must
    # execute (lines 691-700 of app.py).
    from epy_slides.design_block_dialog import DesignBlockDialog

    monkeypatch.setattr(
        DesignBlockDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )
    monkeypatch.setattr(
        DesignBlockDialog, "selected_kind", lambda self: "stat"
    )
    dispatched: dict = {}
    monkeypatch.setattr(
        window,
        "_on_active_tab",
        lambda action, *args: dispatched.update(action=action, args=args),
    )
    window._open_design_block_picker()
    assert dispatched.get("action") == "insert_design_block"
    assert dispatched.get("args") == ("stat",)


def test_open_design_block_picker_cancelled_is_noop(window, monkeypatch):
    # Rejected dialog → early return; _on_active_tab must not be called.
    from epy_slides.design_block_dialog import DesignBlockDialog

    monkeypatch.setattr(
        DesignBlockDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )
    dispatched: dict = {}
    monkeypatch.setattr(
        window,
        "_on_active_tab",
        lambda action, *args: dispatched.update(action=action, args=args),
    )
    window._open_design_block_picker()
    assert dispatched == {}
