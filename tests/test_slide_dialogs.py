import pytest
from PySide6.QtWidgets import QApplication

from epy_slides.slide_dialogs import (
    BulletListDialog,
    NewSlideDialog,
    QuoteDialog,
    SpeakerNotesDialog,
    TwoColumnDialog,
)

_USER_ROLE = 0x0100


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def _select_layout(dlg: NewSlideDialog, layout_id: str) -> None:
    for i in range(dlg._list.count()):
        if dlg._list.item(i).data(_USER_ROLE) == layout_id:
            dlg._list.setCurrentRow(i)
            return


def test_new_slide_every_layout_builds(qapp):
    dlg = NewSlideDialog()
    for i in range(dlg._list.count()):
        dlg._list.setCurrentRow(i)
        md = dlg.build_markdown().strip()
        assert md.startswith("#")


def test_new_slide_two_column_skeleton(qapp):
    dlg = NewSlideDialog()
    _select_layout(dlg, "two-column")
    dlg._title.setText("Cmp")
    md = dlg.build_markdown()
    assert ".columns" in md
    assert "<!-- layout: two-column -->" in md
    assert "Cmp" in md


def test_new_slide_image_substitution(qapp):
    dlg = NewSlideDialog()
    _select_layout(dlg, "image-caption")
    dlg._image.setText("figures/x.png")
    dlg._caption.setText("My cap")
    md = dlg.build_markdown()
    assert "figures/x.png" in md
    assert "My cap" in md


def test_bullet_incremental(qapp):
    dlg = BulletListDialog()
    dlg._count.setValue(2)
    dlg._incremental.setChecked(True)
    md = dlg.build_markdown()
    assert "::: {.incremental}" in md
    assert md.count("- Item") == 2


def test_bullet_numbered(qapp):
    dlg = BulletListDialog()
    dlg._count.setValue(3)
    dlg._ordered.setChecked(True)
    md = dlg.build_markdown()
    assert "1. Item 1" in md


def test_two_column_split(qapp):
    dlg = TwoColumnDialog()
    dlg._split.setValue(60)
    md = dlg.build_markdown()
    assert 'width="60%"' in md
    assert 'width="40%"' in md


def test_quote_attribution(qapp):
    dlg = QuoteDialog()
    dlg._quote.setPlainText("Hello")
    dlg._attribution.setText("Me")
    md = dlg.build_markdown()
    assert "> Hello" in md
    assert "— Me" in md


def test_speaker_notes(qapp):
    dlg = SpeakerNotesDialog()
    dlg._text.setPlainText("a note")
    md = dlg.build_markdown()
    assert "::: {.notes}" in md
    assert "a note" in md
