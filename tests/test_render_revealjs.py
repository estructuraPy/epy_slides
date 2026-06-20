from epy_slides import themes
from epy_slides._revealjs_theme import reveal_css_for
from epy_slides.epyson import is_dark
from epy_slides.renderer import render_revealjs
from epy_slides.template import (
    DEFAULT_MARGIN,
    _read_margin,
    _watermark_css,
    reveal_config,
)

_DECK = "---\ntitle: T\n---\n\n## A\n\n- x\n\n## B\n"


def test_render_produces_reveal_deck():
    html = render_revealjs(_DECK)
    assert '<div class="reveal">' in html
    assert '<div class="slides">' in html
    # title slide + two content slides
    assert html.count("<section") >= 3
    assert "new Reveal(" in html


def test_render_embeds_theme_css():
    html = render_revealjs(
        "## A\n", theme_css=reveal_css_for(themes.get("corporate"))
    )
    assert "--r-background-color" in html


def test_render_title_from_front_matter():
    html = render_revealjs(_DECK)
    assert "<title>T</title>" in html
    assert "title-slide" in html


def test_is_dark_light_and_dark():
    assert is_dark("#ffffff") is False
    assert is_dark("#0b0b0b") is True
    assert is_dark([255, 255, 255]) is False
    assert is_dark("not-a-color") is False
    assert is_dark(None) is False


def test_read_margin_default_and_parsing():
    assert _read_margin({}) == DEFAULT_MARGIN
    assert _read_margin({"margin": "0.1"}) == 0.1
    assert _read_margin({"margin": "8%"}) == 0.08
    assert _read_margin({"margin": "9"}) == 0.3  # clamped to the max
    assert _read_margin({"margin": "junk"}) == DEFAULT_MARGIN


def test_reveal_config_margin_from_front_matter():
    cfg = reveal_config(
        {"margin": "0.12"}, width=960, height=540, for_export=False
    )
    assert cfg["margin"] == 0.12
    default = reveal_config({}, width=960, height=540, for_export=False)
    assert default["margin"] == DEFAULT_MARGIN


def test_watermark_css_absent_is_empty():
    assert _watermark_css({}) == ""


def test_watermark_css_light_theme_uses_multiply():
    light = reveal_css_for(themes.get("corporate"))
    css = _watermark_css({"watermark": "logo.png"}, light)
    assert "mix-blend-mode: multiply" in css
    assert "grayscale(1)" not in css
    assert "opacity: 0.12" in css
    # full-bleed slides always get a difference blend so they never wash out
    assert "slide-image-fullbleed::after" in css
    assert "mix-blend-mode: difference" in css


def test_watermark_css_dark_theme_inverts():
    dark_css = "--r-background-color: #101014;"
    css = _watermark_css({"watermark": "logo.png"}, dark_css)
    assert "mix-blend-mode: screen" in css
    assert "invert(1)" in css


def test_watermark_opacity_override():
    light = reveal_css_for(themes.get("corporate"))
    css = _watermark_css(
        {"watermark": "logo.png", "watermark-opacity": "0.3"}, light
    )
    assert "opacity: 0.3" in css
