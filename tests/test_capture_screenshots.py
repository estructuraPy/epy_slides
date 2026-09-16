"""Tests for the dev-only screenshot-regeneration script.

``capture_screenshots`` renders real dialogs and the main window offscreen
and grabs them to PNG files for the bundled user manual. Every capture
function resolves its output paths through the module-level ``OUT``
constant (the only path baked in at import time from ``ROOT``), so every
test here monkeypatches ``OUT`` to a ``tmp_path`` before calling anything
that writes a screenshot, and never lets a capture reach the real
``src/epy_slides/_config/_assets/screenshots`` tree.
"""

from __future__ import annotations

import runpy

import pytest
from PIL import Image
from PySide6.QtCore import QElapsedTimer
from PySide6.QtWidgets import QApplication, QWidget

from epy_slides._core import _i18n as i18n
from epy_slides._core._packaging import capture_screenshots as cs
from epy_slides._ui.tab import MarkdownTab
from epy_slides.app import SlideWindow

EXPECTED_DIALOG_STEMS = [
    "dlg_new_slide",
    "presentation_properties",
    "dlg_figure",
    "dlg_table",
    "dlg_equation",
    "dlg_theme",
    "dlg_theme_gallery",
]


@pytest.fixture
def window(qapp):
    """Build a SlideWindow and clean up its tabs afterwards.

    Mirrors the ``window`` fixture in ``tests/test_app.py``.
    """
    win = SlideWindow()
    yield win
    for i in range(win.tabs.count()):
        widget = win.tabs.widget(i)
        if isinstance(widget, MarkdownTab):
            widget.cleanup_preview_tmp()
    win.deleteLater()


def _cleanup_slide_window(win: SlideWindow) -> None:
    for i in range(win.tabs.count()):
        widget = win.tabs.widget(i)
        if isinstance(widget, MarkdownTab):
            widget.cleanup_preview_tmp()
    win.deleteLater()


# ------------------------------------------------------------------ pump


def test_pump_spins_the_event_loop_for_at_least_ms(qapp):
    """``pump`` blocks until its own elapsed timer reaches ``ms``."""
    timer = QElapsedTimer()
    timer.start()
    cs.pump(qapp, 30)
    assert timer.elapsed() >= 30


def test_pump_zero_ms_returns_without_spinning(qapp):
    """Counter-example: ``ms=0`` fails the loop guard on its first check.

    ``timer.elapsed() < ms`` is ``0 < 0`` immediately, so the loop body
    never runs a single ``processEvents`` call instead of spinning.
    """
    timer = QElapsedTimer()
    timer.start()
    cs.pump(qapp, 0)
    assert timer.elapsed() < 30


# ------------------------------------------------------------ grab_widget


def test_grab_widget_writes_a_real_png_at_widget_size(qapp, tmp_path):
    widget = QWidget()
    try:
        widget.resize(120, 80)
        path = tmp_path / "nested" / "widget.png"
        cs.grab_widget(qapp, widget, path, settle=10)

        assert path.exists()
        assert path.stat().st_size > 0
        with Image.open(path) as img:
            assert img.format == "PNG"
            assert img.size == (120, 80)
    finally:
        widget.deleteLater()


def test_grab_widget_prints_name_dimensions_and_byte_size(
    qapp, tmp_path, capsys
):
    widget = QWidget()
    try:
        widget.resize(64, 48)
        path = tmp_path / "widget.png"
        cs.grab_widget(qapp, widget, path, settle=10)

        out = capsys.readouterr().out
        size = path.stat().st_size
        assert "widget.png" in out
        assert "64x48" in out
        assert f"{size:,} B" in out
    finally:
        widget.deleteLater()


def test_grab_widget_creates_missing_parent_directories(qapp, tmp_path):
    widget = QWidget()
    try:
        widget.resize(30, 30)
        nested = tmp_path / "a" / "b" / "c"
        assert not nested.exists()

        cs.grab_widget(qapp, widget, nested / "shot.png", settle=10)

        assert nested.is_dir()
        assert (nested / "shot.png").exists()
    finally:
        widget.deleteLater()


def test_grab_widget_unsupported_extension_saves_nothing(
    qapp, tmp_path, capsys
):
    """Counter-example: an unrecognised suffix makes ``save`` fail.

    Qt infers the PNG/BMP/... writer from the path suffix; an unknown
    one makes ``QPixmap.save`` return ``False`` without creating the
    file, which exercises the ``else 0`` branch of
    ``path.stat().st_size if path.exists() else 0``.
    """
    widget = QWidget()
    try:
        widget.resize(20, 20)
        path = tmp_path / "widget.unknownfmt"
        cs.grab_widget(qapp, widget, path, settle=10)

        assert not path.exists()
        out = capsys.readouterr().out
        assert "0 B" in out
    finally:
        widget.deleteLater()


# ------------------------------------------------------------- sample_meta


def test_sample_meta_returns_the_manual_prefill_values():
    assert cs.sample_meta() == {
        "title": "Quarterly review",
        "subtitle": "Structural engineering update",
        "author": "Ing. Angel Navarro-Mora M.Sc.",
        "date": "2026-06-18",
        "theme": "corporate",
        "aspect-ratio": "16:9",
        "transition": "slide",
        "slide-number": "true",
        "footer": "ANM Ingeniería",
        "copyright": "© 2026 ANM Ingeniería",
    }


# --------------------------------------------------------- capture_dialogs


def test_capture_dialogs_writes_every_manual_dialog(
    monkeypatch, qapp, window, tmp_path
):
    monkeypatch.setattr(cs, "OUT", tmp_path)

    cs.capture_dialogs(qapp, window, "")

    for stem in EXPECTED_DIALOG_STEMS:
        shot = tmp_path / f"{stem}.png"
        assert shot.exists(), stem
        assert shot.stat().st_size > 0
        with Image.open(shot) as img:
            assert img.format == "PNG"


# -------------------------------------------------------- capture_language


def test_capture_language_writes_editor_and_suffixed_dialogs(
    monkeypatch, qapp, window, tmp_path
):
    monkeypatch.setattr(cs, "OUT", tmp_path)
    tab = window._current_tab()
    assert tab is not None
    tab.set_initial_text(cs.DEMO_DECK, path=None)

    cs.capture_language(qapp, window, "_es")

    editor_shot = tmp_path / "editor_es.png"
    assert editor_shot.exists()
    assert editor_shot.stat().st_size > 0
    with Image.open(editor_shot) as img:
        assert img.format == "PNG"

    for stem in EXPECTED_DIALOG_STEMS:
        shot = tmp_path / f"{stem}_es.png"
        assert shot.exists(), stem
        assert shot.stat().st_size > 0

    # The unsuffixed (English) filenames were never touched by this call.
    assert not (tmp_path / "editor.png").exists()


# ----------------------------------------------------------------- main()


def test_main_raises_without_a_real_qapplication_instance(monkeypatch):
    """``main()`` refuses a bare (non-widgets) application singleton.

    ``QApplication.instance()`` always returns the real, already-running
    ``QApplication`` from the session ``qapp`` fixture, so the
    ``isinstance`` guard can only be exercised by forcing ``instance()``
    to hand back something else. This patches only the classmethod, not
    the live singleton, so the shared session app is never replaced.
    """
    monkeypatch.setattr(
        cs.QApplication, "instance", staticmethod(lambda: object())
    )

    with pytest.raises(RuntimeError, match="QApplication"):
        cs.main()


def test_main_app_is_none_branch_constructs_a_new_application(
    monkeypatch, qapp
):
    """Exercises the ``app is None`` branch's own construction call.

    In a real standalone run (``python -m ...``) ``QApplication.instance()``
    genuinely returns ``None`` before the first ``QApplication`` exists.
    Inside this shared pytest session a singleton must already exist for
    every other Qt test, so the only way to reach the ``app = QApplication(
    sys.argv)`` line is to report ``None`` once and let ``main()``
    construct a *second* real ``QApplication`` — exactly what that branch
    does. PySide6/shiboken itself refuses that with its own
    ``RuntimeError`` ("...destroy the QApplication singleton before
    creating a new..."), and leaves the existing singleton untouched, so
    the rest of the session is unaffected.
    """
    real_instance = cs.QApplication.instance
    calls = {"n": 0}

    def fake_instance():
        calls["n"] += 1
        return None if calls["n"] == 1 else real_instance()

    monkeypatch.setattr(
        cs.QApplication, "instance", staticmethod(fake_instance)
    )

    with pytest.raises(RuntimeError, match="QApplication singleton"):
        cs.main()

    assert calls["n"] == 1
    assert QApplication.instance() is qapp


def test_main_generates_both_languages_and_prunes_stale_files(
    monkeypatch, qapp, tmp_path
):
    monkeypatch.setattr(cs, "OUT", tmp_path)

    # ``pump`` normally blocks on wall-clock settle times (up to 3.5 s at
    # startup, 1.5 s per editor grab, 250 ms per dialog) so the real
    # preview/paint pipeline settles before a grab. ``main()``'s own
    # control flow — window setup, language toggling, file generation,
    # stale-file pruning — does not depend on how long that settle is,
    # so a near-instant stand-in keeps this test fast without changing
    # what is exercised.
    def fast_pump(app, ms):
        app.processEvents()

    monkeypatch.setattr(cs, "pump", fast_pump)

    # main() schedules ``app.quit()`` on the shared session QApplication
    # via ``QTimer.singleShot`` but never re-enters the event loop
    # afterwards in this process, so that callback should never fire
    # here. Stub it out defensively so this test can never tear down
    # the QApplication every other test in the session shares.
    monkeypatch.setattr(qapp, "quit", lambda: None)

    # Seed one stale variant per stale stem so both branches of the
    # cleanup loop's ``if target.exists()`` guard run for real: some
    # files present (get removed), others absent (skipped, no error).
    stale_present = ["dlg_bib.png", "dlg_footnote_es.png"]
    for name in stale_present:
        (tmp_path / name).write_bytes(b"stale")
    stale_absent = tmp_path / "dlg_xref.png"

    before_windows = set(QApplication.topLevelWidgets())
    original_language = i18n.current_language()
    try:
        result = cs.main()
    finally:
        i18n.set_language(original_language)

    try:
        assert result == 0
        assert (tmp_path / "editor.png").exists()
        assert (tmp_path / "editor_es.png").exists()
        for stem in EXPECTED_DIALOG_STEMS:
            assert (tmp_path / f"{stem}.png").exists()
            assert (tmp_path / f"{stem}_es.png").exists()

        for name in stale_present:
            assert not (tmp_path / name).exists()
        assert not stale_absent.exists()
    finally:
        new_windows = [
            w
            for w in QApplication.topLevelWidgets()
            if w not in before_windows and isinstance(w, SlideWindow)
        ]
        for win in new_windows:
            _cleanup_slide_window(win)


# ------------------------------------------------------ __main__ guard


def test_dunder_main_guard_reaches_raise_systemexit(monkeypatch):
    """``if __name__ == "__main__": raise SystemExit(main())`` executes.

    This line can only run when the module's own ``__name__`` global is
    the literal string ``"__main__"``, which never happens on a normal
    ``import`` -- ``runpy.run_path(..., run_name="__main__")`` is needed
    to actually reach it. That re-executes the file's top level fresh
    (a NEW module namespace, not the cached ``cs`` object), so ``ROOT``/
    ``OUT`` are recomputed from the file's REAL path -- there is no seam
    in this fresh namespace to redirect them to ``tmp_path`` the way the
    other ``main()`` tests do.

    Reusing that redirection is unnecessary here: ``QApplication`` is
    the same shared class object in every namespace (PySide6 is already
    imported and cached), so patching its ``instance`` classmethod
    -- exactly as ``test_main_raises_without_a_real_qapplication_instance``
    already does against the cached module -- makes the freshly executed
    ``main()`` raise its own ``RuntimeError`` at the very first
    ``isinstance`` check, before it ever constructs a window or touches
    ``OUT``. The line is reached and executed (coverage traces line
    entry, not successful completion), nothing is read from or written
    to the real repository, and the shared session ``QApplication``
    singleton is untouched.
    """
    monkeypatch.setattr(
        QApplication, "instance", staticmethod(lambda: object())
    )

    with pytest.raises(RuntimeError, match="QApplication"):
        runpy.run_path(cs.__file__, run_name="__main__")
