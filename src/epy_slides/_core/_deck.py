"""SlideDeck facade: one deck source that exports to HTML, PPTX and PDF.

Moved out of the package facade (which is a wrap).
"""

from __future__ import annotations

from pathlib import Path


class SlideDeck:
    """One slide-deck source that exports to HTML, PowerPoint and PDF."""

    def __init__(
        self,
        source: str,
        base_dir: Path | None = None,
        theme: str = "corporate",
    ) -> None:
        """Build a deck from slide-structured Markdown ``source``."""
        self.source = source
        self.base_dir = base_dir
        self.theme_id = theme

    @classmethod
    def from_file(
        cls, path: str | Path, theme: str = "corporate"
    ) -> SlideDeck:
        """Build a deck by reading a Markdown file."""
        p = Path(path)
        return cls(
            p.read_text(encoding="utf-8"), base_dir=p.parent, theme=theme
        )

    def _theme_css(self) -> str:
        """Return the reveal CSS for the active theme."""
        from epy_slides._core import themes  # noqa: PLC0415
        from epy_slides._core._revealjs_theme import (
            reveal_css_for,  # noqa: PLC0415
        )

        return reveal_css_for(themes.get(self.theme_id))

    def to_html(self, path: str | Path, *, continuous: bool = False) -> Path:
        """Write a standalone reveal.js slideshow (presentation by default)."""
        from epy_slides._core.renderer import render_revealjs  # noqa: PLC0415

        html = render_revealjs(
            self.source,
            base_dir=self.base_dir,
            theme_css=self._theme_css(),
            for_export=True,
            continuous=continuous,
        )
        out = Path(path)
        out.write_text(html, encoding="utf-8")
        return out

    def to_pptx(self, path: str | Path) -> Path:
        """Write a PowerPoint deck (Pandoc + the theme reference deck)."""
        from epy_slides._core.renderer import export_pptx  # noqa: PLC0415

        out = Path(path)
        export_pptx(
            self.source, out, base_dir=self.base_dir, theme_id=self.theme_id
        )
        return out

    def to_pdf(self, path: str | Path, *, timeout_ms: int = 60000) -> Path:
        """Write a one-slide-per-page PDF (reveal print; needs PySide6)."""
        from epy_slides._core._export_pdf import (
            render_deck_pdf,  # noqa: PLC0415
        )

        out = Path(path)
        render_deck_pdf(
            self.source,
            out,
            base_dir=self.base_dir,
            theme_css=self._theme_css(),
            timeout_ms=timeout_ms,
        )
        return out
