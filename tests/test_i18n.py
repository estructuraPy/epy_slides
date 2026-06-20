"""Tests for the in-app internationalization helpers."""

from __future__ import annotations

import pytest

from epy_slides import _i18n as i18n


@pytest.fixture(autouse=True)
def _restore_language():
    """Reset the module language and observers after every test."""
    saved_lang = i18n.current_language()
    saved_observers = list(i18n._observers)
    yield
    i18n._lang = saved_lang
    i18n._observers[:] = saved_observers


# ------------------------------------------------------------------ tr / state


def test_languages_catalogue():
    assert i18n.LANGUAGES == {"en": "English", "es": "Español"}


def test_tr_english_is_identity():
    i18n.set_language("en")
    assert i18n.tr("&File") == "&File"
    assert i18n.tr("Anything not translated") == "Anything not translated"


def test_tr_spanish_translates_known_key():
    i18n.set_language("es")
    assert i18n.tr("&File") == "&Archivo"


def test_tr_spanish_falls_back_to_source_for_unknown():
    i18n.set_language("es")
    assert i18n.tr("Totally unknown string") == "Totally unknown string"


def test_set_language_ignores_unknown_code():
    i18n.set_language("en")
    i18n.set_language("fr")
    assert i18n.current_language() == "en"


def test_set_language_same_code_is_noop_no_callbacks():
    i18n.set_language("en")
    calls: list[int] = []
    i18n.on_language_changed(lambda: calls.append(1))
    i18n.set_language("en")  # already English → no fire
    assert calls == []


def test_set_language_fires_observers():
    i18n.set_language("en")
    calls: list[str] = []
    i18n.on_language_changed(lambda: calls.append(i18n.current_language()))
    i18n.set_language("es")
    assert calls == ["es"]
    assert i18n.current_language() == "es"


# --------------------------------------------------------------- translate_widget


def test_translate_widget_noop_in_english(qapp):
    from PySide6.QtWidgets import QLabel

    i18n.set_language("en")
    label = QLabel("File")
    i18n.translate_widget(label)
    assert label.text() == "File"


def test_translate_widget_relabels_children(qapp):
    from PySide6.QtWidgets import (
        QGroupBox,
        QLabel,
        QLineEdit,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    i18n.set_language("es")
    root = QWidget()
    root.setWindowTitle("Insert figure")
    layout = QVBoxLayout(root)
    label = QLabel("Caption:")
    button = QPushButton("Cancel")
    box = QGroupBox("Colors")
    field = QLineEdit()
    field.setPlaceholderText("My theme")
    for w in (label, button, box, field):
        layout.addWidget(w)

    i18n.translate_widget(root)

    assert root.windowTitle() == "Insertar figura"
    assert label.text() == "Título:"
    assert button.text() == "Cancelar"
    assert box.title() == "Colores"
    assert field.placeholderText() == "Mi tema"
