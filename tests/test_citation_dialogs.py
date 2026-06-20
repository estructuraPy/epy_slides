"""Dialog tests: BibEntryDialog and CrossRefDialog for epy_slides."""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from epy_slides.bib import BibEntry, BibEntryDraft
from epy_slides.bib_dialog import BibEntryDialog
from epy_slides.snippets import Label
from epy_slides.xref_dialog import CrossRefDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_bib_entry_dialog_creates_without_crash(qapp):
    dlg = BibEntryDialog()
    assert dlg is not None


def test_bib_entry_dialog_default_type(qapp):
    dlg = BibEntryDialog(default_type="article")
    assert dlg.type_combo.currentText() == "article"


def test_bib_entry_dialog_build_draft(qapp):
    dlg = BibEntryDialog()
    dlg._field_edits["author"].setText("Doe, John")
    dlg._field_edits["title"].setText("A test entry")
    dlg._field_edits["year"].setText("2026")
    dlg._field_edits["journal"].setText("Test Journal")
    # Set key last and mark as user-typed so auto-suggest does not overwrite.
    dlg._user_typed_key = True
    dlg._field_edits["key"].setText("test2026")
    draft = dlg.build_draft()
    assert isinstance(draft, BibEntryDraft)
    assert draft.key == "test2026"
    assert draft.author == "Doe, John"


def test_bib_entry_dialog_bibtex_output(qapp):
    dlg = BibEntryDialog()
    dlg._field_edits["key"].setText("smith2025")
    dlg._field_edits["author"].setText("Smith, Jane")
    dlg._field_edits["title"].setText("Some paper")
    dlg._field_edits["year"].setText("2025")
    dlg._field_edits["journal"].setText("JOSE")
    bibtex = dlg.build_bibtex()
    assert "@article{smith2025," in bibtex
    assert "Smith, Jane" in bibtex


def test_bib_entry_dialog_autosuggest_key(qapp):
    dlg = BibEntryDialog()
    dlg._user_typed_key = False
    dlg._field_edits["author"].setText("Navarro, Angel")
    dlg._field_edits["year"].setText("2020")
    dlg._maybe_autosuggest_key()
    assert dlg._field_edits["key"].text() == "navarro2020"


def test_crossref_dialog_shows_citations(qapp):
    entries = [
        BibEntry(
            key="navarro2020",
            type="article",
            author="Navarro, Angel",
            year="2020",
            title="Seismic assessment",
        )
    ]
    labels = [Label(kind="cite", name=e.key) for e in entries]
    bib_lookup = {e.key: e for e in entries}
    dlg = CrossRefDialog(labels, bib_lookup=bib_lookup)
    assert dlg.list_widget.count() == 1
    item_text = dlg.list_widget.item(0).text()
    assert "navarro2020" in item_text


def test_crossref_dialog_filter(qapp):
    entries = [
        BibEntry(
            key="navarro2020", type="article",
            author="Navarro, Angel", year="2020", title="X",
        ),
        BibEntry(
            key="doe2021", type="book",
            author="Doe, John", year="2021", title="Y",
        ),
    ]
    labels = [Label(kind="cite", name=e.key) for e in entries]
    bib_lookup = {e.key: e for e in entries}
    dlg = CrossRefDialog(labels, bib_lookup=bib_lookup)
    dlg.filter_edit.setText("navarro")
    assert dlg.list_widget.count() == 1
    assert "navarro2020" in dlg.list_widget.item(0).text()


def test_crossref_dialog_selected_label(qapp):
    entries = [
        BibEntry(
            key="navarro2020", type="article",
            author="Navarro, Angel", year="2020", title="X",
        ),
    ]
    labels = [Label(kind="cite", name=e.key) for e in entries]
    bib_lookup = {e.key: e for e in entries}
    dlg = CrossRefDialog(labels, bib_lookup=bib_lookup)
    dlg.list_widget.setCurrentRow(0)
    label = dlg.selected_label()
    assert label is not None
    assert label.name == "navarro2020"
    assert label.kind == "cite"
