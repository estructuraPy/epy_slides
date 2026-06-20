from epy_slides import themes
from epy_slides._revealjs_theme import reveal_css_for


def test_reveal_css_has_core_tokens():
    css = reveal_css_for(themes.get("corporate"))
    for token in (
        "--r-background-color",
        "--r-main-color",
        "--r-heading-color",
        "--r-link-color",
        ".reveal .columns",
        ".reveal .callout-note",
    ):
        assert token in css


def test_reveal_css_differs_by_theme():
    corporate = reveal_css_for(themes.get("corporate"))
    scientific = reveal_css_for(themes.get("scientific"))
    assert corporate != scientific


def test_reveal_css_covers_all_callouts():
    css = reveal_css_for(themes.get("academic"))
    for kind in ("note", "tip", "warning", "important", "caution"):
        assert f".reveal .callout-{kind}" in css


def test_reveal_css_big_stat_is_responsive():
    css = reveal_css_for(themes.get("corporate"))
    # Figures shrink as more stats share the row so they keep fitting.
    assert ".stats:has(.stat:nth-child(4)) .stat strong" in css
    assert ".stats:has(.stat:nth-child(5)) .stat strong" in css
    # Numbers never wrap mid-value and columns may shrink below content.
    assert "white-space: nowrap" in css
    assert "min-width: 0" in css
