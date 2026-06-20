"""Tests for the theme catalogue facade and the Theme dataclass."""

from __future__ import annotations

from epy_slides import themes
from epy_slides.themes import DEFAULT_THEME_ID, THEMES, Theme, get, reload
from epy_slides.themes_base import Theme as BaseTheme


# --------------------------------------------------------------- Theme dataclass


def test_theme_dataclass_to_css():
    theme = BaseTheme(
        id="x", display_name="X",
        qt_palette={}, css_vars={"bg": "#fff", "fg": "#000"},
    )
    css = theme.to_css()
    assert css.startswith(":root {")
    assert "--bg: #fff;" in css
    assert "--fg: #000;" in css
    assert css.rstrip().endswith("}")


def test_theme_dataclass_to_css_empty():
    theme = BaseTheme(id="x", display_name="X", qt_palette={}, css_vars={})
    assert theme.to_css() == ""


def test_theme_alias_is_base_theme():
    assert Theme is BaseTheme


# --------------------------------------------------------------- catalogue


def test_themes_dict_populated():
    assert len(THEMES) >= 9
    assert DEFAULT_THEME_ID in THEMES


def test_get_known_id():
    theme = get("corporate")
    assert theme.id == "corporate"


def test_get_unknown_id_falls_back_to_default():
    theme = get("no-such-theme")
    assert theme.id == DEFAULT_THEME_ID


def test_get_none_falls_back_to_default():
    assert get(None).id == DEFAULT_THEME_ID


def test_get_empty_when_no_default(monkeypatch):
    """When the default id is missing, get() returns any registered theme."""
    fake = {"alpha": THEMES[DEFAULT_THEME_ID]}
    monkeypatch.setattr(themes, "THEMES", fake)
    monkeypatch.setattr(themes, "DEFAULT_THEME_ID", "missing")
    result = themes.get("also-missing")
    assert result.id in {"corporate", DEFAULT_THEME_ID}


def test_get_last_resort_fallback(monkeypatch):
    """With no themes at all, get() returns an empty fallback Theme."""
    monkeypatch.setattr(themes, "THEMES", {})
    monkeypatch.setattr(themes, "DEFAULT_THEME_ID", "missing")
    result = themes.get(None)
    assert result.id == "fallback"
    assert result.qt_palette == {}
    assert result.css_vars == {}


# --------------------------------------------------------------- reload


def test_reload_returns_same_dict_instance():
    before = THEMES
    result = reload()
    assert result is THEMES
    assert before is THEMES  # not rebound
    assert DEFAULT_THEME_ID in THEMES
