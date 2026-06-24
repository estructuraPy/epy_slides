"""Tests for the MarkdownTab editor widget's text-manipulation API.

The tab embeds a live ``QWebEngineView`` preview; the rendering path runs
asynchronously and is not asserted here. These tests cover the synchronous
editor operations: buffer state, dirty tracking, file I/O, the text-wrapping
and heading commands, the snippet inserters and the bibliography helpers.
"""

from __future__ import annotations

import pytest

from epy_slides.tab import UNTITLED, MarkdownTab


@pytest.fixture
def tab(qapp):
    """Build a fresh MarkdownTab, cleaning up its preview temp dir after."""
    widget = MarkdownTab()
    yield widget
    widget.cleanup_preview_tmp()
    widget.deleteLater()


# --------------------------------------------------------------- buffer state


def test_new_tab_is_untitled_and_clean(tab):
    assert tab.path is None
    assert tab.dirty is False
    assert tab.title() == UNTITLED
    assert tab.text() == ""


def test_set_initial_text_resets_dirty(tab):
    tab.set_initial_text("# Hello\n")
    assert tab.text() == "# Hello\n"
    assert tab.dirty is False
    assert tab.title() == UNTITLED


def test_edit_marks_dirty_and_title_starred(tab):
    tab.set_initial_text("base\n")
    tab.editor.setPlainText("edited")
    assert tab.dirty is True
    assert tab.title().endswith(" *")


def test_dirty_changed_signal(tab):
    flips: list[bool] = []
    tab.dirtyChanged.connect(flips.append)
    tab.set_initial_text("x")
    tab.editor.setPlainText("y")
    assert True in flips


# --------------------------------------------------------------- file I/O


def test_save_without_path_returns_false(tab):
    tab.set_initial_text("content")
    assert tab.save() is False


def test_save_as_then_save(tab, tmp_path):
    tab.set_initial_text("hello world")
    target = tmp_path / "deck.md"
    tab.save_as(target)
    assert tab.path == target
    assert target.read_text(encoding="utf-8") == "hello world"
    assert tab.dirty is False
    assert tab.title() == "deck.md"

    tab.editor.setPlainText("changed")
    assert tab.dirty is True
    assert tab.save() is True
    assert target.read_text(encoding="utf-8") == "changed"
    assert tab.dirty is False


def test_load_file(tab, tmp_path):
    src = tmp_path / "in.md"
    src.write_text("## Slide\n", encoding="utf-8")
    tab.load_file(src)
    assert tab.text() == "## Slide\n"
    assert tab.path == src
    assert tab.dirty is False


def test_reload_discards_changes(tab, tmp_path):
    src = tmp_path / "r.md"
    src.write_text("original", encoding="utf-8")
    tab.load_file(src)
    tab.editor.setPlainText("scratch")
    assert tab.dirty is True
    tab.reload()
    assert tab.text() == "original"
    assert tab.dirty is False


def test_reload_without_path_is_noop(tab):
    tab.set_initial_text("buf")
    tab.reload()  # no path → no-op, must not raise
    assert tab.text() == "buf"


# --------------------------------------------------------------- formatting


def test_toggle_bold_inserts_markers_at_caret(tab):
    tab.set_initial_text("")
    tab.toggle_bold()
    assert "**bold**" in tab.text()


def test_toggle_bold_wraps_selection(tab):
    tab.set_initial_text("word")
    cursor = tab.editor.textCursor()
    cursor.select(cursor.SelectionType.Document)
    tab.editor.setTextCursor(cursor)
    tab.toggle_bold()
    assert tab.text() == "**word**"


def test_toggle_italic_and_inline_code(tab):
    tab.set_initial_text("")
    tab.toggle_italic()
    assert "*italic*" in tab.text()
    tab.set_initial_text("")
    tab.toggle_inline_code()
    assert "`code`" in tab.text()


def test_set_heading_level_applies_prefix(tab):
    tab.set_initial_text("My title")
    tab.set_heading_level(2)
    assert tab.text().startswith("## My title")


def test_set_heading_level_replaces_existing(tab):
    tab.set_initial_text("### Old")
    tab.set_heading_level(1)
    assert tab.text().startswith("# Old")
    assert "###" not in tab.text()


def test_set_heading_level_zero_removes_heading(tab):
    tab.set_initial_text("## Heading")
    tab.set_heading_level(0)
    assert tab.text() == "Heading"


def test_set_heading_level_clamped_to_six(tab):
    tab.set_initial_text("Deep")
    tab.set_heading_level(9)
    assert tab.text().startswith("###### Deep")


def test_insert_link_at_caret(tab):
    tab.set_initial_text("")
    tab.insert_link()
    assert "[TEXT](URL)" in tab.text()


def test_insert_link_wraps_selection(tab):
    tab.set_initial_text("anchor")
    cursor = tab.editor.textCursor()
    cursor.select(cursor.SelectionType.Document)
    tab.editor.setTextCursor(cursor)
    tab.insert_link()
    assert "[anchor](URL)" in tab.text()


# ------------------------------------------------------------- snippet blocks


def test_insert_code_block(tab):
    tab.set_initial_text("")
    tab.insert_code_block()
    assert "```python" in tab.text()


def test_insert_slide_break(tab):
    tab.set_initial_text("a")
    tab.insert_slide_break()
    assert "---" in tab.text()


def test_insert_diagram_mermaid_and_nomnoml(tab):
    tab.set_initial_text("")
    tab.insert_diagram("mermaid")
    assert "```mermaid" in tab.text()
    tab.set_initial_text("")
    tab.insert_diagram("nomnoml")
    assert "```nomnoml" in tab.text()


def test_insert_diagram_unknown_engine_defaults_mermaid(tab):
    tab.set_initial_text("")
    tab.insert_diagram("bogus")
    assert "```mermaid" in tab.text()


def test_next_label_suffix_method(tab):
    tab.set_initial_text("![a](a.png){#fig-1}\n![b](b.png){#fig-2}\n")
    assert tab._next_label_suffix("fig") == "3"
    assert tab._next_label_suffix("tbl") == "1"


# --------------------------------------------------------------- bibliography


def test_bib_path_none_when_no_front_matter(tab):
    tab.set_initial_text("## Slide\n")
    assert tab.bib_path() is None


def test_bib_entries_empty_without_bib(tab):
    tab.set_initial_text("## Slide\n")
    assert tab.bib_entries() == []


def test_link_bibliography_writes_relative_path(tab, tmp_path):
    deck = tmp_path / "deck.md"
    deck.write_text("## Slide\n", encoding="utf-8")
    tab.load_file(deck)
    bib = tmp_path / "refs.bib"
    bib.write_text("", encoding="utf-8")
    tab.link_bibliography(bib)
    assert "bibliography: refs.bib" in tab.text()


def test_bib_path_resolves_relative(tab, tmp_path):
    deck = tmp_path / "deck.md"
    bib = tmp_path / "refs.bib"
    bib.write_text(
        "@book{x, title={T}, author={A}, year={2020}}\n", encoding="utf-8"
    )
    deck.write_text(
        "---\nbibliography: refs.bib\n---\n\n## Slide\n", encoding="utf-8"
    )
    tab.load_file(deck)
    resolved = tab.bib_path()
    assert resolved == bib
    entries = tab.bib_entries()
    assert len(entries) == 1


# --------------------------------------------------------------- misc


def test_set_theme_css_stores_value(tab):
    tab.set_initial_text("## A\n")
    tab.set_theme_css(":root{--epy-bg:#fff;}")
    assert tab._theme_css == ":root{--epy-bg:#fff;}"


def test_store_position_ignores_empty(tab):
    tab._store_position("")
    assert tab._last_pos == ""
    tab._store_position("epypos=v:1.0")
    assert tab._last_pos == "epypos=v:1.0"
    tab._store_position(None)
    assert tab._last_pos == "epypos=v:1.0"  # unchanged


def test_cleanup_preview_tmp_is_idempotent(tab):
    tab.set_initial_text("## A\n")  # creates the preview temp dir
    tab.cleanup_preview_tmp()
    tab.cleanup_preview_tmp()  # second call must be a no-op
