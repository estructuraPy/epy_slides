"""Tests for the Markdown snippet, label and front-matter helpers."""

from __future__ import annotations

from epy_slides import snippets
from epy_slides.snippets import (
    KIND_DESCRIPTIONS,
    Label,
    find_labels,
    parse_front_matter,
    parse_header_cells,
    set_metadata_field,
)


# --------------------------------------------------------------- find_labels


def test_find_labels_extracts_each_kind():
    text = (
        "![a](a.png){#fig-one width=80%}\n"
        ": cap {#tbl-two}\n"
        "$$x$$ {#eq-three}\n"
        "## H {#sec-four}"
    )
    labels = find_labels(text)
    assert labels == [
        Label(kind="fig", name="fig-one"),
        Label(kind="tbl", name="tbl-two"),
        Label(kind="eq", name="eq-three"),
        Label(kind="sec", name="sec-four"),
    ]


def test_find_labels_deduplicates_preserving_order():
    text = "{#fig-a}\n{#fig-b}\n{#fig-a}"
    names = [label.name for label in find_labels(text)]
    assert names == ["fig-a", "fig-b"]


def test_find_labels_empty_text():
    assert find_labels("") == []


def test_label_is_frozen_dataclass():
    label = Label(kind="fig", name="fig-x")
    assert label.kind == "fig"
    assert label.name == "fig-x"


def test_kind_descriptions_cover_all_kinds():
    assert set(KIND_DESCRIPTIONS) == {"fig", "tbl", "eq", "sec"}


# ------------------------------------------------------------ templates exist


def test_templates_carry_placeholder_tokens():
    assert "{#fig-LABEL" in snippets.FIGURE_TEMPLATE
    assert "{#tbl-LABEL}" in snippets.TABLE_TEMPLATE
    assert "{#eq-LABEL}" in snippets.EQUATION_TEMPLATE
    assert "CODE" in snippets.CODE_BLOCK_TEMPLATE
    assert "TEXT" in snippets.LINK_TEMPLATE and "URL" in snippets.LINK_TEMPLATE
    assert "{#sec-LABEL}" in snippets.SECTION_HEADING_TEMPLATE


def test_callout_templates_cover_five_kinds():
    assert set(snippets.CALLOUT_TEMPLATES) == {
        "note", "tip", "warning", "important", "caution",
    }
    assert "callout-note" in snippets.CALLOUT_TEMPLATES["note"]
    assert 'title="TITLE"' in snippets.CALLOUT_TEMPLATES["tip"]


def test_primary_placeholder_targets():
    assert snippets.PRIMARY_PLACEHOLDER["figure"] == "LABEL"
    assert snippets.PRIMARY_PLACEHOLDER["code"] == "CODE"
    assert snippets.PRIMARY_PLACEHOLDER["callout"] == "TITLE"


def test_image_markdown_format():
    md = snippets.IMAGE_MARKDOWN.format(
        caption="Beam", path="figures/b.png", label="b", width="70%"
    )
    assert md == "![Beam](figures/b.png){#fig-b width=70%}"


# ---------------------------------------------------------- parse_front_matter


def test_parse_front_matter_reads_top_level_scalars():
    text = "---\ntitle: My Deck\nauthor: ANM\n---\n\nBody"
    meta = parse_front_matter(text)
    assert meta == {"title": "My Deck", "author": "ANM"}


def test_parse_front_matter_strips_quotes():
    text = '---\ntitle: "Quoted"\nfoo: \'bar\'\n---\n'
    meta = parse_front_matter(text)
    assert meta["title"] == "Quoted"
    assert meta["foo"] == "bar"


def test_parse_front_matter_skips_comments_indented_and_listless():
    text = (
        "---\n"
        "# a comment\n"
        "title: Deck\n"
        "  indented: skipped\n"
        "noColon\n"
        "---\n"
    )
    meta = parse_front_matter(text)
    assert meta == {"title": "Deck"}


def test_parse_front_matter_no_block_returns_empty():
    assert parse_front_matter("No front matter here") == {}


def test_parse_front_matter_unterminated_block_returns_empty():
    assert parse_front_matter("---\ntitle: x\n") == {}


# ---------------------------------------------------------- parse_header_cells


def test_parse_header_cells_from_list():
    assert parse_header_cells(["A", 1, "B"]) == ["A", "1", "B"]


def test_parse_header_cells_from_json_string():
    assert parse_header_cells('["A", "B", "C"]') == ["A", "B", "C"]


def test_parse_header_cells_from_invalid_json_string():
    # A bracketed but non-JSON value is treated as a single cell.
    assert parse_header_cells("[oops") == ["[oops"]


def test_parse_header_cells_plain_string():
    assert parse_header_cells("Just one") == ["Just one"]


def test_parse_header_cells_empty():
    assert parse_header_cells("") == []
    assert parse_header_cells(None) == []


# ---------------------------------------------------------- set_metadata_field


def test_set_metadata_field_creates_block_when_absent():
    out = set_metadata_field("Body text", "title", "Deck")
    assert out.startswith("---\ntitle: Deck\n---\n\n")
    assert out.endswith("Body text")


def test_set_metadata_field_replaces_existing_value():
    text = "---\ntitle: Old\nauthor: ANM\n---\nBody"
    out = set_metadata_field(text, "title", "New")
    assert "title: New" in out
    assert "title: Old" not in out
    assert "author: ANM" in out


def test_set_metadata_field_appends_when_missing_in_block():
    text = "---\ntitle: Deck\n---\nBody"
    out = set_metadata_field(text, "author", "ANM")
    assert "title: Deck" in out
    assert "author: ANM" in out


def test_set_metadata_field_quotes_ambiguous_value():
    out = set_metadata_field("Body", "subtitle", "a: b")
    assert 'subtitle: "a: b"' in out


def test_set_metadata_field_raw_value_not_quoted():
    out = set_metadata_field("Body", "header", '["A", "B"]', raw=True)
    assert 'header: ["A", "B"]' in out


def test_set_metadata_field_empty_value_is_quoted():
    out = set_metadata_field("Body", "footer", "")
    assert 'footer: ""' in out
