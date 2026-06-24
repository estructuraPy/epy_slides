"""Snippet-inserter tests for MarkdownTab.

Each inserter opens a small modal then drops Markdown at the caret. The
modals are stubbed (``QDialog.exec`` accepted, ``QInputDialog`` /
``QFileDialog`` returning fixed values) so the synchronous insertion is
exercised headlessly and the resulting buffer text is asserted. The live
reveal preview render is not driven here.
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
def accept(monkeypatch):
    """Make every QDialog.exec() report Accepted."""
    monkeypatch.setattr(
        tab_module.QDialog, "exec",
        lambda self: QDialog.DialogCode.Accepted,
    )


# --------------------------------------------------------- no-dialog inserts


def test_insert_slide_break(tab):
    tab.insert_slide_break()
    assert "---" in tab.text()


def test_insert_diagram_mermaid(tab):
    tab.insert_diagram("mermaid")
    assert "```mermaid" in tab.text()
    assert "flowchart" in tab.text()


def test_insert_diagram_nomnoml(tab):
    tab.insert_diagram("nomnoml")
    assert "```nomnoml" in tab.text()


def test_insert_diagram_unknown_falls_back_to_mermaid(tab):
    tab.insert_diagram("bogus")
    assert "```mermaid" in tab.text()


# ------------------------------------------------------ dialog-gated inserts


def test_insert_new_slide(tab, accept):
    tab.insert_new_slide()
    # A slide skeleton always contains a level-2 heading.
    assert "##" in tab.text()


def test_insert_bullet_list(tab, accept):
    tab.insert_bullet_list()
    assert tab.text().strip() != ""


def test_insert_speaker_notes(tab, accept):
    tab.insert_speaker_notes()
    assert "notes" in tab.text().lower()


def test_insert_two_column(tab, accept):
    tab.insert_two_column()
    assert ".columns" in tab.text() or ".column" in tab.text()


def test_insert_quote(tab, accept):
    tab.insert_quote()
    assert tab.text().strip() != ""


def test_insert_figure_uses_next_label(tab, accept):
    tab.set_initial_text("![a](x.png){#fig-3 width=80%}\n")
    tab.insert_figure()
    # The new figure label increments past the existing fig-3.
    assert "#fig-4" in tab.text()


def test_insert_table_inserts_pipe_table(tab, accept):
    tab.set_initial_text("## Slide\n")
    tab.insert_table()
    # The default TableDialog has no caption, so no {#tbl-} anchor is
    # emitted; the pipe-table header row is still inserted at the caret.
    assert "| Header 1 |" in tab.text()


def test_insert_equation_uses_next_label(tab, accept):
    tab.set_initial_text("## Slide\n")
    tab.insert_equation()
    assert "#eq-1" in tab.text()


def test_insert_checklist(tab, accept):
    tab.insert_checklist()
    # A checklist renders as task-list items.
    assert "- [" in tab.text()


def test_insert_callout_with_title(tab, monkeypatch):
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: ("Heads up", True)),
    )
    tab.insert_callout("warning")
    assert ".callout-warning" in tab.text()
    assert "Heads up" in tab.text()


def test_insert_callout_note_has_no_title_prompt(tab):
    # The note template has no TITLE token, so no prompt is needed.
    tab.insert_callout("note")
    assert ".callout-note" in tab.text()


def test_insert_image_from_dialog_copies_and_links(tab, tmp_path, monkeypatch):
    img = tmp_path / "pic.png"
    img.write_bytes(b"\x89PNG\r\n\x1a\n")
    deck = tmp_path / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    tab.load_file(deck)

    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: (str(img), "")),
    )
    answers = iter([("My caption", True), ("60%", True)])
    monkeypatch.setattr(
        QInputDialog, "getText",
        staticmethod(lambda *a, **k: next(answers)),
    )
    tab.insert_image_from_dialog()
    text = tab.text()
    assert "My caption" in text
    assert "width=60%" in text
    assert (tmp_path / "figures" / "pic.png").is_file()
