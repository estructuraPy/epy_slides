import pytest
from PySide6.QtCore import QSize
from PySide6.QtWidgets import QApplication

from epy_slides import themes
from epy_slides._previews import (
    LAYOUT_THUMB,
    THEME_THUMB,
    layout_preview,
    theme_preview,
)
from epy_slides.slide_dialogs import LAYOUT_INFO


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_layout_preview_for_every_layout(qapp):
    for layout_id, _label, _desc in LAYOUT_INFO:
        pix = layout_preview(layout_id)
        assert not pix.isNull()
        assert pix.size() == LAYOUT_THUMB


def test_layout_preview_unknown_id_falls_back(qapp):
    pix = layout_preview("no-such-layout")
    assert not pix.isNull()
    assert pix.size() == LAYOUT_THUMB


def test_layout_preview_custom_size(qapp):
    pix = layout_preview("section", QSize(48, 30))
    assert pix.size() == QSize(48, 30)


def test_theme_preview_for_every_theme(qapp):
    assert themes.THEMES, "the theme catalogue must not be empty"
    for theme in themes.THEMES.values():
        pix = theme_preview(theme)
        assert not pix.isNull()
        assert pix.size() == THEME_THUMB


def test_theme_preview_custom_size(qapp):
    theme = themes.get("corporate")
    pix = theme_preview(theme, QSize(120, 76))
    assert pix.size() == QSize(120, 76)
