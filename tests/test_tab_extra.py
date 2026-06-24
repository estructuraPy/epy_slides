"""Extra MarkdownTab branch coverage.

Covers the cancelled-dialog short circuits, the file-picker cancel paths,
the bibliography relative-path fallback, the design-block inserter, the
duplicate-image counter, and the small render/position internals — all
synchronous controller logic, with modals and the web view stubbed.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QDialog, QFileDialog, QInputDialog

from epy_slides import tab as tab_module
from epy_slides.tab import MarkdownTab


@pytest.fixture
def tab(qapp):
    """Build a fresh MarkdownTab, cleaning its preview temp dir after."""
    widget = MarkdownTab()
    yield widget
    widget.cleanup_preview_tmp()
    widget.deleteLater()


@pytest.fixture
def reject(monkeypatch):
    """Make every QDialog.exec() report Rejected."""
    monkeypatch.setattr(
        tab_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Rejected,
    )


# ---------------------------------------------- cancelled dialog inserts


def test_insert_new_slide_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_new_slide()
    assert tab.text() == "base\n"


def test_insert_bullet_list_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_bullet_list()
    assert tab.text() == "base\n"


def test_insert_speaker_notes_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_speaker_notes()
    assert tab.text() == "base\n"


def test_insert_two_column_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_two_column()
    assert tab.text() == "base\n"


def test_insert_quote_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_quote()
    assert tab.text() == "base\n"


def test_insert_figure_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_figure()
    assert tab.text() == "base\n"


def test_insert_table_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_table()
    assert tab.text() == "base\n"


def test_insert_equation_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_equation()
    assert tab.text() == "base\n"


def test_insert_checklist_cancelled(tab, reject):
    tab.set_initial_text("base\n")
    tab.insert_checklist()
    assert tab.text() == "base\n"


def test_insert_image_from_dialog_cancelled(tab, monkeypatch):
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    tab.set_initial_text("base\n")
    tab.insert_image_from_dialog()
    assert tab.text() == "base\n"


# ---------------------------------------------------- image dedup + width


def test_insert_image_dedup_counter_and_default_width(
    tab, tmp_path, monkeypatch
):
    # A second image with the same name gets a ``-1`` suffix, and a cancelled
    # width prompt falls back to the 70% default.
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    deck = tmp_path / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    tab.load_file(deck)
    # Pre-existing figures/pic.png forces the dedup counter.
    figdir = tmp_path / "figures"
    figdir.mkdir()
    (figdir / "pic.png").write_bytes(b"old")

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(img), "")),
    )
    # Caption accepted; width prompt cancelled (ok=False) → default width.
    answers = iter([("Cap", True), ("", False)])
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: next(answers)),
    )
    tab.insert_image_from_dialog()
    text = tab.text()
    assert "pic-1.png" in text
    assert "width=70%" in text
    assert (figdir / "pic-1.png").is_file()


# ------------------------------------------------ bibliography path fallback


def test_link_bibliography_absolute_when_outside_deck_dir(
    tab, tmp_path, monkeypatch
):
    # A .bib outside the deck's directory cannot be made relative, so the
    # absolute path is written (the ValueError fallback branch).
    deck_dir = tmp_path / "proj"
    deck_dir.mkdir()
    deck = deck_dir / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    tab.load_file(deck)
    other = tmp_path / "elsewhere" / "refs.bib"
    other.parent.mkdir()
    other.write_text("", encoding="utf-8")
    tab.link_bibliography(other)
    assert "refs.bib" in tab.text()
    # The stored value is the absolute path (posix-normalised).
    assert other.as_posix() in tab.text() or str(other) in tab.text()


# ------------------------------------------------------ design block insert


def test_insert_design_block_inserts_skeleton(tab):
    tab.set_initial_text("")
    tab.insert_design_block("stat")
    assert tab.text().strip() != ""


def test_insert_block_prepends_newline_when_midline(tab):
    # _insert_block adds a leading newline when the caret is not at the start
    # of a line so the block begins on its own line.
    tab.set_initial_text("heading")
    cursor = tab.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    tab.editor.setTextCursor(cursor)
    tab.insert_slide_break()  # delegates to _insert_block
    assert tab.text().startswith("heading\n")
    assert "---" in tab.text()


def test_insert_template_prepends_newline_when_midline(tab):
    # When the caret is not at the start of a line, a multi-line template
    # is preceded by a newline so it begins on its own line.
    tab.set_initial_text("prefix")
    cursor = tab.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    tab.editor.setTextCursor(cursor)
    tab.insert_design_block("stat")
    assert tab.text().startswith("prefix\n")


def test_setup_editor_falls_back_to_consolas(qapp, monkeypatch):
    # When the system fixed font reports an invalid size (Qt clamps real
    # QFonts, so use a stub that reports 0), the editor falls back to
    # Consolas (the size-guard branch in _setup_editor). After the guard the
    # code builds a real QFont("Consolas"), so the stub only needs pointSize.
    from PySide6.QtGui import QFontDatabase

    class _TinyFont:
        def pointSize(self):  # noqa: N802
            return 0

    monkeypatch.setattr(
        QFontDatabase, "systemFont", staticmethod(lambda _which: _TinyFont())
    )
    widget = MarkdownTab()
    try:
        # The fallback set Consolas at 11pt without raising.
        assert widget.editor.font().pointSize() == 11
    finally:
        widget.cleanup_preview_tmp()
        widget.deleteLater()


# ---------------------------------------------------- render / position


def test_render_scheduled_renders(tab):
    tab.set_initial_text("## A\n")
    tab._last_pos = "epypos=v:1.0"
    tab._render_scheduled()  # must not raise (preserve render)


def test_poll_position_runs_when_page_present(tab, monkeypatch):
    tab.set_initial_text("## A\n")
    captured: dict = {}

    class _FakePage:
        def runJavaScript(self, _expr, cb):  # noqa: N802
            captured["called"] = True
            cb("epypos=v:2.1")

    monkeypatch.setattr(tab.view, "page", lambda: _FakePage())
    tab._poll_position()
    assert captured.get("called") is True
    assert tab._last_pos == "epypos=v:2.1"


def test_poll_position_skips_when_no_page(tab, monkeypatch):
    monkeypatch.setattr(tab.view, "page", lambda: None)
    tab._poll_position()  # must not raise


def test_store_position_records_valid_token(tab):
    tab._store_position("epypos=v:3.0")
    assert tab._last_pos == "epypos=v:3.0"
