"""Tests for the PPTX component simplification (no Qt required)."""

from __future__ import annotations

from epy_slides.slide_md import simplify_components_for_export

STATS = """\
:::: {.stats}
::: {.stat}
**98%**

[on schedule]{.stat-label}
:::
::: {.stat}
**3**

[open risks]{.stat-label}
:::
::::
"""

CARDS = """\
:::: {.cards}
::: {.card}
#### Strength
Characteristic value.
:::
::: {.card}
#### Stiffness
Within limits.
:::
::::
"""


def test_stats_become_a_pipe_table():
    out = simplify_components_for_export(STATS)
    assert "| **98%** | **3** |" in out
    assert "| on schedule | open risks |" in out
    # The fenced-div wrappers are gone.
    assert "{.stats}" not in out
    assert "{.stat}" not in out


def test_cards_become_bold_titled_blocks():
    out = simplify_components_for_export(CARDS)
    assert "**Strength**" in out
    assert "Characteristic value." in out
    assert "#### Strength" not in out
    assert "{.card}" not in out


def test_timeline_is_unwrapped_to_a_list():
    src = "::: {.timeline}\n- **1929** Excavation\n- **1931** Opening\n:::\n"
    out = simplify_components_for_export(src)
    assert "- **1929** Excavation" in out
    assert "{.timeline}" not in out
    assert ":::" not in out


def test_callouts_and_columns_are_preserved():
    src = (
        "::: {.callout-note title=\"Keep\"}\nBody.\n:::\n\n"
        ":::: {.columns}\n::: {.column width=\"50%\"}\nL\n:::\n"
        "::: {.column width=\"50%\"}\nR\n:::\n::::\n"
    )
    out = simplify_components_for_export(src)
    assert ".callout-note" in out
    assert "{.columns}" in out
    assert '{.column width="50%"}' in out


def test_plain_text_is_unchanged():
    src = "## Title\n\nA paragraph with **bold** and a list:\n\n- one\n- two\n"
    assert simplify_components_for_export(src) == src
