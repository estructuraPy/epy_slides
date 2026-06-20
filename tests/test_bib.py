"""Tests for the bib parser and writer."""

from __future__ import annotations

from pathlib import Path

from epy_slides.bib import (
    BibEntryDraft,
    append_entry_to_file,
    keys_in_file,
    parse_bib_file,
    parse_bib_text,
    serialize_draft,
    suggest_key,
)

_SAMPLE_BIB = """\
@article{navarro2020,
  author = {Navarro, Angel},
  title  = {Seismic assessment},
  journal = {JOSE},
  year   = {2020},
}

@book{doe2021,
  author    = {Doe, John},
  title     = {Structural dynamics},
  publisher = {Wiley},
  year      = {2021},
}
"""


def test_parse_bib_text_finds_entries():
    entries = parse_bib_text(_SAMPLE_BIB)
    assert len(entries) == 2
    keys = {e.key for e in entries}
    assert "navarro2020" in keys
    assert "doe2021" in keys


def test_parse_bib_entry_fields():
    entries = parse_bib_text(_SAMPLE_BIB)
    navarro = next(e for e in entries if e.key == "navarro2020")
    assert navarro.type == "article"
    assert "Navarro" in navarro.author
    assert navarro.year == "2020"


def test_short_label():
    entries = parse_bib_text(_SAMPLE_BIB)
    navarro = next(e for e in entries if e.key == "navarro2020")
    label = navarro.short_label()
    assert "@navarro2020" in label
    assert "2020" in label


def test_suggest_key():
    assert suggest_key("Navarro, Angel", "2020") == "navarro2020"
    assert suggest_key("", "") == ""


def test_serialize_draft_roundtrip():
    draft = BibEntryDraft(
        type="article",
        key="test2026",
        author="Test, Author",
        title="A test article",
        journal="Test Journal",
        year="2026",
    )
    bib_text = serialize_draft(draft)
    assert "@article{test2026," in bib_text
    assert "author" in bib_text
    assert "2026" in bib_text


def test_parse_bib_file_not_found():
    result = parse_bib_file(Path("/nonexistent/path.bib"))
    assert result == []


def test_append_and_keys(tmp_path):
    bib_file = tmp_path / "refs.bib"
    draft = BibEntryDraft(
        type="misc",
        key="smith2025",
        author="Smith, Jane",
        title="A misc entry",
        year="2025",
    )
    append_entry_to_file(bib_file, draft)
    assert bib_file.exists()
    keys = keys_in_file(bib_file)
    assert "smith2025" in keys


def test_append_idempotent_separator(tmp_path):
    bib_file = tmp_path / "refs.bib"
    d1 = BibEntryDraft(
        type="misc", key="a2024", title="First", year="2024"
    )
    d2 = BibEntryDraft(
        type="misc", key="b2024", title="Second", year="2024"
    )
    append_entry_to_file(bib_file, d1)
    append_entry_to_file(bib_file, d2)
    content = bib_file.read_text(encoding="utf-8")
    assert content.count("@misc") == 2
