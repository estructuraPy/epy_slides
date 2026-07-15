"""Extra branch coverage for dialog file-pickers and validators.

Covers the ``_browse`` / ``_pick_image`` file-picker slots (stubbed
``QFileDialog`` statics), the colour-button picker, the theme-editor name
validator, the bibliography reference-hint branches and the cross-ref
non-citation / empty-filter / no-selection paths. All run headlessly.
"""

from __future__ import annotations

from epy_slides.snippets import Label
from epy_slides.xref_dialog import CrossRefDialog

# ------------------------------------------------------- about_dialog branding


def test_load_branding_pixmap_missing_resource_is_empty(qapp, monkeypatch):
    from epy_slides import about_dialog

    def boom(_package):
        raise FileNotFoundError("no branding")

    monkeypatch.setattr(
        about_dialog.importlib.resources, "files", boom
    )
    pix = about_dialog._load_branding_pixmap("missing.png")
    assert pix.isNull()


# ------------------------------------------------------- figure_dialog browse


def test_figure_dialog_browse_sets_path(qapp, monkeypatch):
    from epy_slides import figure_dialog
    from epy_slides.figure_dialog import FigureDialog

    dlg = FigureDialog()
    monkeypatch.setattr(
        figure_dialog.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("C:/pics/logo.png", "")),
    )
    dlg._browse()
    assert dlg.path_edit.text() == "C:/pics/logo.png"


def test_figure_dialog_browse_cancelled_keeps_path(qapp, monkeypatch):
    from epy_slides import figure_dialog
    from epy_slides.figure_dialog import FigureDialog

    dlg = FigureDialog()
    dlg.path_edit.setText("keep.png")
    monkeypatch.setattr(
        figure_dialog.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    dlg._browse()
    assert dlg.path_edit.text() == "keep.png"


# --------------------------------------- presentation_properties pick image


def test_presentation_properties_pick_image(qapp, monkeypatch):
    from PySide6.QtWidgets import QLineEdit

    from epy_slides import presentation_properties_dialog as ppd
    from epy_slides.presentation_properties_dialog import (
        PresentationPropertiesDialog,
    )

    dlg = PresentationPropertiesDialog(meta={})
    edit = QLineEdit()
    monkeypatch.setattr(
        ppd.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("C:/img/cover.png", "")),
    )
    dlg._pick_image(edit)
    assert edit.text() == "C:/img/cover.png"


def test_presentation_properties_pick_image_cancelled(qapp, monkeypatch):
    from PySide6.QtWidgets import QLineEdit

    from epy_slides import presentation_properties_dialog as ppd
    from epy_slides.presentation_properties_dialog import (
        PresentationPropertiesDialog,
    )

    dlg = PresentationPropertiesDialog(meta={})
    edit = QLineEdit()
    edit.setText("old.png")
    monkeypatch.setattr(
        ppd.QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    dlg._pick_image(edit)
    assert edit.text() == "old.png"


# --------------------------------------------------- slide_dialogs pick image


def test_new_slide_dialog_pick_image(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from epy_slides.slide_dialogs import NewSlideDialog

    dlg = NewSlideDialog()
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("C:/img/pic.png", "")),
    )
    dlg._pick_image()
    assert dlg._image.text() == "C:/img/pic.png"


def test_new_slide_dialog_pick_image_cancelled(qapp, monkeypatch):
    from PySide6.QtWidgets import QFileDialog

    from epy_slides.slide_dialogs import NewSlideDialog

    dlg = NewSlideDialog()
    dlg._image.setText("keep.png")
    monkeypatch.setattr(
        QFileDialog, "getOpenFileName",
        staticmethod(lambda *a, **k: ("", "")),
    )
    dlg._pick_image()
    assert dlg._image.text() == "keep.png"


# --------------------------------------------------- theme_editor_dialog


def test_pt_value_invalid_returns_default():
    from epy_slides.theme_editor_dialog import _pt_value

    # "1.2.3" cleans to "1.2.3" which float() rejects → the 12.0 default.
    assert _pt_value("1.2.3pt") == 12.0


def test_color_button_pick_applies_valid_color(qapp, monkeypatch):
    from PySide6.QtGui import QColor

    from epy_slides import theme_editor_dialog as ted
    from epy_slides.theme_editor_dialog import _ColorButton

    btn = _ColorButton("#101010")
    monkeypatch.setattr(
        ted.QColorDialog, "getColor",
        staticmethod(lambda *a, **k: QColor("#ABCDEF")),
    )
    fired = {"n": 0}
    btn.changed.connect(lambda: fired.update(n=fired["n"] + 1))
    btn._pick()
    assert btn.color() == "#ABCDEF"
    assert fired["n"] == 1


def test_color_button_pick_invalid_color_is_noop(qapp, monkeypatch):
    from PySide6.QtGui import QColor

    from epy_slides import theme_editor_dialog as ted
    from epy_slides.theme_editor_dialog import _ColorButton

    btn = _ColorButton("#101010")
    monkeypatch.setattr(
        ted.QColorDialog, "getColor",
        staticmethod(lambda *a, **k: QColor()),  # invalid (cancelled)
    )
    btn._pick()
    assert btn.color() == "#101010"


def test_theme_editor_on_save_empty_name_warns(qapp, monkeypatch):
    from PySide6.QtWidgets import QMessageBox

    from epy_slides.theme_editor_dialog import ThemeEditorDialog

    dlg = ThemeEditorDialog()
    monkeypatch.setattr(dlg, "theme_name", lambda: "")
    warned = {"n": 0}
    monkeypatch.setattr(
        QMessageBox, "warning",
        staticmethod(lambda *a, **k: warned.update(n=warned["n"] + 1)),
    )
    accepted = {"n": 0}
    monkeypatch.setattr(dlg, "accept", lambda: accepted.update(n=1))
    dlg._on_save()
    assert warned["n"] == 1
    assert accepted["n"] == 0


def test_theme_editor_on_save_valid_name_accepts(qapp, monkeypatch):
    from epy_slides.theme_editor_dialog import ThemeEditorDialog

    dlg = ThemeEditorDialog()
    monkeypatch.setattr(dlg, "theme_name", lambda: "House Style")
    accepted = {"n": 0}
    monkeypatch.setattr(dlg, "accept", lambda: accepted.update(n=1))
    dlg._on_save()
    assert accepted["n"] == 1


# ------------------------------------------------------- xref_dialog branches


def test_crossref_non_citation_label_shows_kind(qapp):
    labels = [Label(kind="fig", name="fig-1")]
    dlg = CrossRefDialog(labels)
    assert dlg.list_widget.count() == 1
    text = dlg.list_widget.item(0).text()
    assert "fig-1" in text


def test_crossref_empty_filter_shows_all(qapp):
    labels = [
        Label(kind="fig", name="fig-1"),
        Label(kind="tbl", name="tbl-1"),
    ]
    dlg = CrossRefDialog(labels)
    dlg.filter_edit.setText("fig")
    dlg.filter_edit.setText("")  # back to empty → all labels visible
    assert dlg.list_widget.count() == 2


def test_crossref_selected_label_none_when_empty(qapp):
    dlg = CrossRefDialog([])
    dlg.list_widget.setCurrentRow(-1)
    assert dlg.selected_label() is None


def test_crossref_cite_without_bib_entry_uses_key(qapp):
    # A cite label with no matching bib entry shows the @key fallback.
    labels = [Label(kind="cite", name="ghost2020")]
    dlg = CrossRefDialog(labels, bib_lookup={})
    text = dlg.list_widget.item(0).text()
    assert "@ghost2020" in text
