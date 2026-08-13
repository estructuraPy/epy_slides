"""Tests for epy_slides._ui.xref_dialog.CrossRefDialog.

Mirrors ``src/epy_slides/_ui/xref_dialog.py`` per housekeeper.py's
``audit_module_mirror`` (module-level tests-mirror DNA). Split out of
test_citation_dialogs.py (which also covered bib_dialog.BibEntryDialog,
now in test_bib_dialog.py); complements the non-citation / empty-filter /
no-selection branch coverage already in test_dialogs_extra.py with the
citation-lookup path.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from epy_slides._core.bib import BibEntry
from epy_slides._core.snippets import Label
from epy_slides._ui.xref_dialog import CrossRefDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


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
