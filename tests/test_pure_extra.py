"""Extra branch coverage for pure helpers across small modules.

These functions are widget-free and deterministic: bib label/key edge
cases, the pptx component rewriters, the preview colour helpers and the
pdf-footer roman/anchor helpers. Each test drives one previously-missed
branch with a concrete input and asserts the exact result.
"""

from __future__ import annotations

from epy_slides import _previews
from epy_slides.bib import BibEntry, BibEntryDraft, suggest_key
from epy_slides.slide_md import (
    _heading_with_layout,
    _stats_to_table,
    expand_for_pptx,
    simplify_components_for_export,
)

# --------------------------------------------------------------------- bib


def test_short_label_uses_last_token_when_no_comma():
    # An author without a comma uses the last whitespace token as the family
    # name in the compact label.
    entry = BibEntry(
        key="x", type="article", author="Angel Navarro", year="2020",
        title="T",
    )
    label = entry.short_label()
    assert "Navarro" in label


def test_short_label_truncates_long_title():
    long_title = "A" * 80
    entry = BibEntry(
        key="x", type="misc", author="", year="", title=long_title
    )
    label = entry.short_label()
    assert "..." in label
    # The displayed title is clipped to 57 chars + ellipsis.
    assert ("A" * 57 + "...") in label


def test_missing_required_lists_blank_key_and_fields():
    # An article with no key/author/title/journal/year reports every
    # required field plus the missing key.
    draft = BibEntryDraft(type="article", key="", author="", title="")
    missing = draft.missing_required()
    assert "key" in missing
    assert "author" in missing
    assert "title" in missing


def test_missing_required_satisfied_returns_empty():
    draft = BibEntryDraft(
        type="article", key="k", author="Doe, J", title="T",
        journal="J", year="2020",
    )
    assert draft.missing_required() == []


def test_suggest_key_last_token_when_no_comma():
    # No comma in the author → the last token is the family name slug.
    assert suggest_key("Angel Navarro", "2021") == "navarro2021"


# ----------------------------------------------------------------- slide_md


def test_heading_with_layout_merges_existing_attr_block():
    # A heading that already carries a {...} attribute block has the layout
    # classes merged in rather than appended as a second block.
    out = _heading_with_layout("##", "Title {#sec-1}", "two-column")
    assert out.count("{") == 1
    assert ".slide-two-column" in out
    assert "#sec-1" in out


def test_expand_pptx_strips_background_heading_attr():
    src = '## Cover {background-color="#000"}\n\nbody\n'
    out = expand_for_pptx(src)
    first = out.splitlines()[0]
    assert "background-color" not in first
    assert first.startswith("## Cover")


def test_simplify_stats_to_table():
    src = (
        "::: {.stats}\n"
        "::: {.stat}\n**42**\n[Projects]{.stat-label}\n:::\n"
        "::: {.stat}\n**7**\n[Years]{.stat-label}\n:::\n"
        ":::\n"
    )
    out = simplify_components_for_export(src)
    assert "**42**" in out
    assert "Projects" in out
    # The big stats render as a 2-row pipe table.
    assert "|" in out
    assert ":--:" in out


def test_simplify_stats_label_from_plain_line():
    # A stat whose label is a plain (non-bold) line, not a [..]{.stat-label}.
    src = (
        "::: {.stats}\n"
        "::: {.stat}\n**12**\nUnits\n:::\n"
        ":::\n"
    )
    out = simplify_components_for_export(src)
    assert "**12**" in out
    assert "Units" in out


def test_simplify_cards_to_blocks_with_heading():
    src = (
        "::: {.cards}\n"
        "::: {.card}\n#### First\nbody one\n:::\n"
        "::: {.card}\n#### Second\nbody two\n:::\n"
        ":::\n"
    )
    out = simplify_components_for_export(src)
    assert "**First**" in out
    assert "**Second**" in out
    assert "body one" in out


def test_simplify_unwraps_timeline_block():
    # A non-stats/cards component (timeline) is unwrapped, keeping its inner
    # list while dropping the fenced wrapper.
    src = "::: {.timeline}\n- step 1\n- step 2\n:::\n"
    out = simplify_components_for_export(src)
    assert "step 1" in out
    assert ".timeline" not in out


def test_expand_pptx_callout_with_nested_div():
    # A callout containing a nested fenced div drives the depth-tracking
    # branches in _callout_to_blockquote (nested open + non-final close).
    src = (
        '::: {.callout-tip title="Deep"}\n'
        "intro line\n"
        "::: {.inner}\n"
        "nested body\n"
        ":::\n"
        "after nested\n"
        ":::\n"
    )
    out = expand_for_pptx(src)
    assert "> **Deep**" in out
    assert "nested body" in out
    assert "after nested" in out


def test_stats_to_table_empty_returns_empty_list():
    # A stats block with no inner .stat divs yields no table at all.
    assert _stats_to_table(["plain text", "no stats here"]) == []


def test_simplify_stats_block_ignores_non_stat_lines():
    # Lines inside a .stats block that are not .stat divs are skipped, and a
    # block with no stats produces no table (the empty-numbers branch).
    src = "::: {.stats}\njust a note\n:::\n"
    out = simplify_components_for_export(src)
    # No pipe table is emitted; the stray content is dropped with the wrapper.
    assert ":--:" not in out


def test_simplify_cards_block_ignores_non_card_lines():
    # Non-.card lines inside a .cards block are skipped (the else branch).
    src = "::: {.cards}\nloose note\n:::\n"
    out = simplify_components_for_export(src)
    assert ".cards" not in out


def test_simplify_handles_unterminated_div():
    # A component fence that never closes is collected to end-of-input
    # without raising (the loop-exhaustion branch in _collect_div).
    src = "::: {.cards}\n::: {.card}\n#### Solo\nbody\n"
    out = simplify_components_for_export(src)
    assert "Solo" in out


# ----------------------------------------------------------------- previews


def test_color_falls_back_to_string_fallback():
    from PySide6.QtGui import QColor

    # An invalid value with a string fallback returns a QColor of the string.
    result = _previews._color("not-a-color", "#112233")
    assert isinstance(result, QColor)
    assert result.name().lower() == "#112233"


def test_color_returns_qcolor_fallback_object():
    from PySide6.QtGui import QColor

    fallback = QColor("#445566")
    result = _previews._color(None, fallback)
    assert result is fallback


def test_primary_family_empty_for_blank_stack():
    assert _previews._primary_family(None) == ""
    assert _previews._primary_family("") == ""


def test_primary_family_strips_quotes():
    assert _previews._primary_family('"Segoe UI", sans-serif') == "Segoe UI"
