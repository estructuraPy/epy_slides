"""Tests for the epyson theme loader, user-theme storage and palette apply.

The colour-math helpers and ``qss_for`` are covered by ``test_themes_qss``;
this file targets the loaders, the ``build_epyson`` form serialiser, the
user-theme directory round-trip and ``apply_palette``.
"""

from __future__ import annotations

import json

import pytest

from epy_slides import epyson
from epy_slides.epyson import (
    _coerce_hex,
    _contrast_text,
    _font_stack,
    _pt,
    _rgb_to_hex,
    _safe_stem,
    build_epyson,
    delete_user_theme,
    is_dark,
    load_layout_theme,
    load_user_theme,
    save_user_theme,
    user_theme_ids,
    user_themes_dir,
)
from epy_slides.themes_base import Theme


@pytest.fixture
def isolated_user_dir(tmp_path, monkeypatch):
    """Redirect the user-theme directory at a temp path for the test."""
    target = tmp_path / "themes"
    monkeypatch.setattr(epyson, "user_themes_dir", lambda: target)
    return target


# --------------------------------------------------------------- small helpers


def test_rgb_to_hex():
    assert _rgb_to_hex([0, 33, 126]) == "#00217E"


def test_coerce_hex_from_string_with_hash():
    assert _coerce_hex("#ABCDEF") == "#ABCDEF"


def test_coerce_hex_from_string_without_hash():
    assert _coerce_hex("ABCDEF") == "#ABCDEF"


def test_coerce_hex_from_rgb_list():
    assert _coerce_hex([255, 0, 0]) == "#FF0000"


def test_contrast_text_picks_black_on_light():
    assert _contrast_text("#FFFFFF") == "#000000"


def test_contrast_text_picks_white_on_dark():
    assert _contrast_text("#000000") == "#FFFFFF"


def test_font_stack_uses_defaults():
    assert _font_stack({}) == '"Calibri", Arial, sans-serif'


def test_font_stack_uses_given_primary_and_fallback():
    stack = _font_stack({"primary": "Georgia", "fallback": "serif"})
    assert stack == '"Georgia", serif'


def test_pt_returns_size_and_weight():
    size, weight = _pt({"h1": {"size": 24, "weight": 700}}, "h1", 12)
    assert size == "24pt"
    assert weight == "700"


def test_pt_uses_defaults_when_role_missing():
    size, weight = _pt({}, "h1", 18)
    assert size == "18pt"
    assert weight == "400"


# --------------------------------------------------------------- is_dark guard


def test_is_dark_none_is_light():
    assert is_dark(None) is False


def test_is_dark_unparseable_is_light():
    assert is_dark("not-a-color") is False


def test_is_dark_accepts_rgb_triplet():
    assert is_dark([0, 0, 0]) is True
    assert is_dark([255, 255, 255]) is False


# --------------------------------------------------------------- layout loader


def test_load_layout_theme_returns_theme():
    theme = load_layout_theme("corporate.epyson")
    assert isinstance(theme, Theme)
    assert theme.id == "corporate"
    assert theme.css_vars["bg"].startswith("#")
    assert "Window" in theme.qt_palette
    # Callout vars are resolved from the palette catalogue.
    assert "callout-note-bg" in theme.css_vars


# --------------------------------------------------------------- build_epyson


def _form_values() -> dict:
    return {
        "display_name": "My Theme",
        "page_bg": "#FFFFFF",
        "text": "#101010",
        "heading": "#00217E",
        "primary": "#0050C8",
        "secondary": "#0969DA",
        "border": "#C8C8C8",
        "code_bg": "#F5F5F5",
        "mark": "#CA9A24",
        "text_font": "Calibri",
        "code_font": "Consolas",
        "scales": {
            "h1": {"size": 24.0, "weight": "700"},
            "text": {"size": 12.0, "weight": "400"},
        },
        "callouts": {
            "note": {"bg": "#EAF2FB", "border": "#2F6FBF"},
        },
    }


def test_build_epyson_shape_and_round_trip():
    payload = build_epyson(_form_values())
    assert payload["display_name"] == "My Theme"
    assert payload["palette"]["page"]["background"] == [255, 255, 255]
    assert payload["palette"]["colors"]["primary"] == [0, 80, 200]
    assert payload["font_families"]["default"]["primary"] == "Calibri"
    assert payload["callouts"]["types"]["note"]["bg"] == "#EAF2FB"
    # The payload must load back into a coherent Theme.
    theme = epyson._theme_from_raw(payload, "my-theme")
    assert theme.display_name == "My Theme"
    assert theme.css_vars["callout-note-bg"] == "#EAF2FB"


# --------------------------------------------------- user-theme directory I/O


def test_user_theme_ids_empty_when_no_dir(isolated_user_dir):
    assert user_theme_ids() == set()


def test_save_and_load_user_theme_round_trip(isolated_user_dir):
    payload = build_epyson(_form_values())
    theme_id = save_user_theme(payload)
    assert theme_id == "my-theme"
    assert isolated_user_dir.is_dir()
    assert theme_id in user_theme_ids()

    path = isolated_user_dir / f"{theme_id}.epyson"
    loaded = load_user_theme(path)
    assert loaded.id == "my-theme"
    assert loaded.display_name == "My Theme"


def test_delete_user_theme(isolated_user_dir):
    payload = build_epyson(_form_values())
    theme_id = save_user_theme(payload)
    assert theme_id in user_theme_ids()
    delete_user_theme(theme_id)
    assert theme_id not in user_theme_ids()


def test_delete_user_theme_missing_is_noop(isolated_user_dir):
    delete_user_theme("does-not-exist")  # must not raise


def test_user_theme_ids_skips_corrupt_files(isolated_user_dir):
    isolated_user_dir.mkdir(parents=True, exist_ok=True)
    (isolated_user_dir / "broken.epyson").write_text("{ not json")
    good = build_epyson(_form_values())
    (isolated_user_dir / "good.epyson").write_text(
        json.dumps({**good, "layout_name": "good"})
    )
    ids = user_theme_ids()
    assert "good" in ids
    assert "broken" not in ids


def test_safe_stem_slugifies():
    assert _safe_stem("My Cool Theme!") == "my-cool-theme"
    assert _safe_stem("   ") == "custom-theme"


# ----------------------------------------------------- user_themes_dir (real)


def test_user_themes_dir_is_under_epy_slides(qapp):
    # Real call (needs a QApplication for QStandardPaths) — must point at an
    # epy_slides/themes subtree.
    path = user_themes_dir()
    assert path.name == "themes"
    assert path.parent.name == "epy_slides"


# --------------------------------------------------------------- apply_palette


def test_apply_palette_sets_window_color(qapp):
    from PySide6.QtGui import QPalette

    theme = load_layout_theme("corporate.epyson")
    epyson.apply_palette(qapp, theme)
    window = qapp.palette().color(QPalette.ColorRole.Window).name().upper()
    assert window == theme.qt_palette["Window"].upper()
