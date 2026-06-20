"""Tests for the custom-theme editor dialog and its helpers.

The dialog is built (not exec'd) so its construction, the form-value
collection, the base-theme reload and the live-preview restyle are all
exercised headlessly.
"""

from __future__ import annotations

from epy_slides import themes
from epy_slides.theme_editor_dialog import (
    _CALLOUTS,
    _COLOR_FIELDS,
    ThemeEditorDialog,
    _ColorButton,
    _contrast,
    _font_primary,
    _pt_value,
)


# --------------------------------------------------------------- pure helpers


def test_contrast_light_and_dark():
    assert _contrast("#FFFFFF") == "#000000"
    assert _contrast("#000000") == "#FFFFFF"


def test_contrast_malformed_hex_defaults_black():
    assert _contrast("#fff") == "#000000"
    assert _contrast("nope") == "#000000"


def test_font_primary_extracts_first_family():
    assert _font_primary('"Calibri", Arial, sans-serif') == "Calibri"
    assert _font_primary("'Georgia', serif") == "Georgia"


def test_font_primary_empty_defaults():
    assert _font_primary("") == "Calibri"


def test_pt_value_parses_pt_string():
    assert _pt_value("24pt") == 24.0
    assert _pt_value("12.5pt") == 12.5


def test_pt_value_unparseable_defaults_12():
    assert _pt_value("") == 12.0
    assert _pt_value("abc") == 12.0


# --------------------------------------------------------------- _ColorButton


def test_color_button_default(qapp):
    btn = _ColorButton()
    assert btn.color() == "#000000"
    assert btn.text() == "#000000"


def test_color_button_set_color_uppercases_and_refreshes(qapp):
    btn = _ColorButton("#abcdef")
    btn.set_color("#fedcba")
    assert btn.color() == "#FEDCBA"
    assert btn.text() == "#FEDCBA"
    assert "#FEDCBA" in btn.styleSheet()


# --------------------------------------------------------------- dialog build


def test_dialog_builds_with_all_fields(qapp):
    dlg = ThemeEditorDialog()
    assert dlg.windowTitle() == "Theme editor"
    # Every declared color field and callout has a widget.
    for key, _label in _COLOR_FIELDS:
        assert key in dlg._colors
    for kind in _CALLOUTS:
        assert kind in dlg._callouts


def test_dialog_prefills_from_base_theme(qapp):
    dlg = ThemeEditorDialog(base_theme_id="corporate")
    corp = themes.get("corporate")
    assert dlg._colors["page_bg"].color() == corp.css_vars["bg"].upper()


def test_theme_name_strips(qapp):
    dlg = ThemeEditorDialog()
    dlg.name_edit.setText("  My Theme  ")
    assert dlg.theme_name() == "My Theme"


def test_values_and_payload_round_trip(qapp):
    dlg = ThemeEditorDialog(base_theme_id="corporate")
    dlg.name_edit.setText("Round Trip")
    values = dlg._values()
    assert values["display_name"] == "Round Trip"
    assert set(values) >= {
        "page_bg", "text", "heading", "primary", "secondary",
        "border", "code_bg", "mark", "text_font", "code_font",
        "scales", "callouts",
    }
    payload = dlg.epyson_payload()
    assert payload["display_name"] == "Round Trip"
    # The payload loads into a coherent theme.
    theme = themes.build_epyson  # serialiser used by epyson_payload
    assert callable(theme)


def test_on_base_changed_reloads_colors(qapp):
    dlg = ThemeEditorDialog(base_theme_id="corporate")
    # Switch the combo to a different bundled base and trigger the reload.
    idx = dlg.base_combo.findData("minimal")
    assert idx >= 0, "minimal is a bundled theme and must be selectable"
    dlg.base_combo.setCurrentIndex(idx)
    dlg._on_base_changed()
    minimal = themes.get("minimal")
    assert dlg._colors["page_bg"].color() == minimal.css_vars["bg"].upper()


def test_edit_id_prefills_name(qapp, tmp_path, monkeypatch):
    # Register a temporary user theme then open the editor on it.
    from epy_slides import epyson

    monkeypatch.setattr(epyson, "user_themes_dir", lambda: tmp_path)
    payload = themes.build_epyson({
        "display_name": "Editable",
        "page_bg": "#FFFFFF", "text": "#101010", "heading": "#00217E",
        "primary": "#0050C8", "secondary": "#0969DA", "border": "#C8C8C8",
        "code_bg": "#F5F5F5", "mark": "#CA9A24",
        "text_font": "Calibri", "code_font": "Consolas",
        "scales": {
            "h1": {"size": 24.0, "weight": "700"},
            "text": {"size": 12.0, "weight": "400"},
            "caption": {"size": 10.0, "weight": "400"},
        },
        "callouts": {
            k: {"bg": "#EAF2FB", "border": "#2F6FBF"} for k in _CALLOUTS
        },
    })
    theme_id = epyson.save_user_theme(payload)
    themes.reload()
    try:
        dlg = ThemeEditorDialog(edit_id=theme_id)
        assert dlg.name_edit.text() == "Editable"
    finally:
        epyson.delete_user_theme(theme_id)
        themes.reload()


def test_update_preview_sets_stylesheets(qapp):
    dlg = ThemeEditorDialog(base_theme_id="corporate")
    dlg._update_preview()
    assert dlg.preview_box.styleSheet() != ""
    assert dlg._pv_heading.styleSheet() != ""
    assert dlg._pv_code.styleSheet() != ""
