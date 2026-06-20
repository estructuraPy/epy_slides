import pytest
from PySide6.QtWidgets import QApplication

from epy_slides import themes
from epy_slides.theme_gallery_dialog import ThemeGalleryDialog


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_gallery_lists_every_theme(qapp):
    dlg = ThemeGalleryDialog()
    assert dlg._list.count() == len(themes.THEMES)


def test_gallery_items_carry_swatch_icons(qapp):
    dlg = ThemeGalleryDialog()
    for i in range(dlg._list.count()):
        assert not dlg._list.item(i).icon().isNull()


def test_gallery_preselects_current_theme(qapp):
    target = next(iter(themes.THEMES))
    dlg = ThemeGalleryDialog(current_id=target)
    assert dlg.selected_theme_id() == target


def test_gallery_defaults_to_first_when_no_current(qapp):
    dlg = ThemeGalleryDialog(current_id="does-not-exist")
    assert dlg.selected_theme_id() is not None
