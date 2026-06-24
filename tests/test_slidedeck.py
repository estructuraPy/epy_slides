"""Tests for the public ``SlideDeck`` facade exported by ``epy_slides``.

These exercise the scriptable entry point (``from epy_slides import
SlideDeck``) end to end against real Pandoc: building a deck from a string
and from a file, resolving the theme CSS, and the HTML / PowerPoint
exporters. The PDF exporter is driven separately because it needs an
offscreen Qt WebEngine render.
"""

from __future__ import annotations

from pathlib import Path

from epy_slides import SlideDeck, __version__

_DECK = "---\ntitle: Facade Deck\n---\n\n## One\n\n- a\n\n## Two\n\ntext\n"


def test_public_exports():
    assert isinstance(__version__, str)
    assert SlideDeck.__module__ == "epy_slides"


def test_init_keeps_source_and_theme():
    deck = SlideDeck(_DECK, theme="scientific")
    assert deck.source == _DECK
    assert deck.theme_id == "scientific"
    assert deck.base_dir is None


def test_from_file_reads_text_and_sets_base_dir(tmp_path):
    md = tmp_path / "talk.md"
    md.write_text(_DECK, encoding="utf-8")
    deck = SlideDeck.from_file(md, theme="minimal")
    assert deck.source == _DECK
    assert deck.base_dir == tmp_path
    assert deck.theme_id == "minimal"


def test_from_file_accepts_str_path(tmp_path):
    md = tmp_path / "talk.md"
    md.write_text(_DECK, encoding="utf-8")
    deck = SlideDeck.from_file(str(md))
    assert deck.source == _DECK
    # Default theme is corporate.
    assert deck.theme_id == "corporate"


def test_theme_css_is_reveal_css_for_theme(qapp):
    deck = SlideDeck(_DECK, theme="corporate")
    css = deck._theme_css()
    assert "--r-background-color" in css
    assert "--r-main-color" in css


def test_to_html_writes_standalone_reveal_deck(qapp, tmp_path):
    out = tmp_path / "talk.html"
    result = SlideDeck(_DECK).to_html(out)
    assert result == out
    assert out.is_file()
    html = out.read_text(encoding="utf-8")
    assert '<div class="reveal">' in html
    assert "new Reveal(" in html
    assert "<title>Facade Deck</title>" in html


def test_to_html_continuous_mode(qapp, tmp_path):
    out = tmp_path / "scroll.html"
    SlideDeck(_DECK).to_html(out, continuous=True)
    html = out.read_text(encoding="utf-8")
    # Continuous (scroll) view is requested in the reveal config.
    assert "scroll" in html.lower()


def test_to_pptx_writes_real_powerpoint(qapp, tmp_path):
    out = tmp_path / "talk.pptx"
    result = SlideDeck(_DECK).to_pptx(out)
    assert result == out
    assert out.is_file()
    # A .pptx is an OOXML zip: it must start with the PK zip signature.
    assert out.read_bytes()[:2] == b"PK"


def test_to_pdf_delegates_to_render_deck_pdf(qapp, tmp_path, monkeypatch):
    # to_pdf must forward source/out/base_dir/theme_css/timeout to the
    # headless renderer (the real Chromium print is mocked at the boundary).
    captured: dict = {}

    def fake_render(source, out, *, base_dir, theme_css, timeout_ms):
        captured.update(
            source=source,
            out=out,
            base_dir=base_dir,
            theme_css=theme_css,
            timeout_ms=timeout_ms,
        )
        Path(out).write_bytes(b"%PDF-1.4\n")

    monkeypatch.setattr(
        "epy_slides._export_pdf.render_deck_pdf", fake_render
    )
    out = tmp_path / "deck.pdf"
    result = SlideDeck(_DECK, base_dir=tmp_path, theme="minimal").to_pdf(
        out, timeout_ms=1234
    )
    assert result == out
    assert captured["source"] == _DECK
    assert captured["out"] == out
    assert captured["base_dir"] == tmp_path
    assert captured["timeout_ms"] == 1234
    # The theme CSS for "minimal" is resolved and passed through.
    assert "--r-background-color" in captured["theme_css"]


def test_to_pptx_respects_resource_path(qapp, tmp_path):
    # base_dir is forwarded so relative image paths resolve; the export
    # must still succeed when an image fence references a local file.
    img = tmp_path / "pic.png"
    # 1x1 transparent PNG.
    img.write_bytes(
        bytes.fromhex(
            "89504e470d0a1a0a0000000d4948445200000001000000010806"
            "0000001f15c4890000000d49444154789c6360000002000100"
            "05fe02fea7e1c5a40000000049454e44ae426082"
        )
    )
    src = "## Slide\n\n![cap](pic.png)\n"
    out = tmp_path / "withimg.pptx"
    SlideDeck(src, base_dir=tmp_path).to_pptx(out)
    assert out.is_file()
    assert out.read_bytes()[:2] == b"PK"
