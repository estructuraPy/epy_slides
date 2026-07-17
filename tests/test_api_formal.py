"""Formal API compliance tests for epy_slides.

Verifies that the public exports are importable, have the expected interface,
and conform to the declared __all__ contract.
"""

from __future__ import annotations

import re

import epy_slides as es

# ---------------------------------------------------------------------------
# Importability
# ---------------------------------------------------------------------------


class TestImportability:
    def test_package_importable(self):
        assert es is not None

    def test_slidedeck_importable(self):
        from epy_slides import SlideDeck

        assert isinstance(SlideDeck, type)


# ---------------------------------------------------------------------------
# Version
# ---------------------------------------------------------------------------


class TestVersion:
    def test_version_attribute_exists(self):
        assert hasattr(es, "__version__")

    def test_version_is_string(self):
        assert isinstance(es.__version__, str)

    def test_version_semver_format(self):
        parts = es.__version__.split(".")
        assert len(parts) == 3, f"Expected 3 version parts, got {parts}"

    def test_version_parts_are_numeric(self):
        for part in es.__version__.split("."):
            assert re.match(r"^\d+", part), f"Non-numeric version part: {part!r}"


# ---------------------------------------------------------------------------
# __all__ contract
# ---------------------------------------------------------------------------


class TestAllContract:
    _EXPECTED = ["SlideDeck", "__version__"]

    def test_all_exists(self):
        assert hasattr(es, "__all__")

    def test_all_matches_declared_contract(self):
        assert sorted(es.__all__) == sorted(self._EXPECTED)

    def test_all_symbols_importable(self):
        for name in es.__all__:
            assert hasattr(es, name), f"__all__ member {name!r} not found on module"


# ---------------------------------------------------------------------------
# SlideDeck facade
# ---------------------------------------------------------------------------


class TestSlideDeckMethods:
    _REQUIRED_METHODS = ["to_html", "to_pptx", "to_pdf"]
    _REQUIRED_CLASSMETHODS = ["from_file"]

    def test_required_methods_present(self):
        from epy_slides import SlideDeck

        for method in self._REQUIRED_METHODS:
            assert hasattr(SlideDeck, method), f"SlideDeck missing: {method!r}"

    def test_required_methods_callable(self):
        from epy_slides import SlideDeck

        for method in self._REQUIRED_METHODS:
            assert callable(getattr(SlideDeck, method)), f"{method!r} is not callable"

    def test_required_classmethods_present(self):
        from epy_slides import SlideDeck

        for method in self._REQUIRED_CLASSMETHODS:
            assert callable(getattr(SlideDeck, method)), f"SlideDeck.{method!r} is not callable"


class TestSlideDeckInit:
    def test_default_theme_is_corporate(self):
        from epy_slides import SlideDeck

        deck = SlideDeck("# Slide 1\n\nBody")
        assert deck.theme_id == "corporate"

    def test_custom_theme_stored(self):
        from epy_slides import SlideDeck

        deck = SlideDeck("# Slide 1\n\nBody", theme="minimal")
        assert deck.theme_id == "minimal"

    def test_source_stored(self):
        from epy_slides import SlideDeck

        deck = SlideDeck("# Slide 1\n\nBody")
        assert deck.source == "# Slide 1\n\nBody"

    def test_from_file_reads_content(self, tmp_path):
        from epy_slides import SlideDeck

        md_file = tmp_path / "sample.md"
        md_file.write_text("# Slide 1\n\nBody", encoding="utf-8")
        deck = SlideDeck.from_file(md_file)
        assert deck.source == "# Slide 1\n\nBody"
        assert deck.base_dir == md_file.parent
