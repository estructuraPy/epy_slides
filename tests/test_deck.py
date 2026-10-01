"""Tests for ``_core/_deck.py`` — the ``SlideDeck`` facade, moved out of the
package ``__init__`` so the facade is a pure wrap."""

from __future__ import annotations

from epy_slides._core._deck import SlideDeck

_DECK = "---\ntitle: Deck\n---\n\n## One\n\ntext\n"


class TestSlideDeckConstruction:
    def test_keeps_source_theme_and_base_dir(self):
        deck = SlideDeck(_DECK, theme="scientific")
        assert deck.source == _DECK
        assert deck.theme_id == "scientific"
        assert deck.base_dir is None

    def test_default_theme_is_corporate(self):
        assert SlideDeck(_DECK).theme_id == "corporate"

    def test_from_file_reads_and_sets_base_dir(self, tmp_path):
        md = tmp_path / "talk.md"
        md.write_text(_DECK, encoding="utf-8")
        deck = SlideDeck.from_file(md, theme="scientific")
        assert deck.source == _DECK
        assert deck.base_dir == tmp_path
        assert deck.theme_id == "scientific"
