import pytest
from PySide6.QtWidgets import QApplication

from epy_slides.presentation_properties_dialog import (
    PresentationPropertiesDialog,
)


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


def test_updates_roundtrip(qapp):
    meta = {
        "title": "T",
        "author": "A",
        "theme": "scientific",
        "aspect-ratio": "4:3",
        "transition": "fade",
        "slide-number": "true",
        "footer": "F",
        "copyright": "C",
    }
    dlg = PresentationPropertiesDialog(None, meta)
    fields = {field: value for field, value, _raw in dlg.updates()}
    assert fields["title"] == "T"
    assert fields["author"] == "A"
    assert fields["theme"] == "scientific"
    assert fields["aspect-ratio"] == "4:3"
    assert fields["transition"] == "fade"
    assert fields["slide-number"] == "true"
    assert fields["footer"] == "F"
    assert fields["copyright"] == "C"


def test_slide_number_unchecked_defaults_false(qapp):
    dlg = PresentationPropertiesDialog(None, {})
    fields = {field: value for field, value, _raw in dlg.updates()}
    assert fields["slide-number"] == "false"
    assert fields["aspect-ratio"] == "16:9"
