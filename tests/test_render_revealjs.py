from epy_slides import themes
from epy_slides._revealjs_theme import reveal_css_for
from epy_slides.renderer import render_revealjs

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
