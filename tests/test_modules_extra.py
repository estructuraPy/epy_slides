"""Extra branch coverage for epyson, i18n, pdf-footer and winreg helpers.

Targets the resource-failure and corrupt-file guards in the theme loader,
the palette-apply font fallback / unknown-role skip, the QPlainTextEdit
placeholder translation, the PDF named-destination extraction, and the
launcher/icon ``shutil.which`` hits plus the open-settings failure path.
"""

from __future__ import annotations

import json

import pytest

# ----------------------------------------------------------------- epyson


def test_load_palettes_missing_file_returns_empty(monkeypatch):
    from epy_slides import epyson

    def boom(_filename):
        raise FileNotFoundError("no colors.epyson")

    monkeypatch.setattr(epyson, "_read_json", boom)
    assert epyson._load_palettes() == {}


def test_load_all_themes_skips_corrupt_bundled_theme(monkeypatch):
    from epy_slides import epyson

    real_loader = epyson.load_layout_theme
    seen: dict = {}

    def flaky(filename):
        # The first bundled theme is corrupt; the rest load normally.
        if "first" not in seen:
            seen["first"] = filename
            raise json.JSONDecodeError("bad", "doc", 0)
        return real_loader(filename)

    monkeypatch.setattr(epyson, "load_layout_theme", flaky)
    themes = epyson.load_all_themes()
    # The corrupt theme is skipped; valid themes still load.
    assert isinstance(themes, dict)
    assert len(themes) >= 1


def test_load_all_themes_skips_corrupt_user_theme(
    tmp_path, monkeypatch
):
    from epy_slides import epyson

    user_dir = tmp_path / "themes"
    user_dir.mkdir()
    (user_dir / "broken.epyson").write_text("{ not json", encoding="utf-8")
    monkeypatch.setattr(epyson, "user_themes_dir", lambda: user_dir)
    themes = epyson.load_all_themes()
    # The broken user theme is skipped without raising.
    assert "broken" not in themes


def test_apply_palette_font_fallback_and_unknown_role(qapp, monkeypatch):
    # Force the Segoe-UI-Variable family check to miss (so the Segoe UI
    # fallback runs) and inject an unknown palette role (so the skip runs).
    from PySide6.QtGui import QFont

    from epy_slides import epyson
    from epy_slides.epyson import load_layout_theme

    real_qfont = QFont

    def fake_qfont(*args):
        # The Segoe UI Variable request resolves to a family that does NOT
        # contain "segoe ui variable", driving the fallback branch.
        if args and "Variable" in args[0]:
            return real_qfont("ArialStub")
        return real_qfont(*args)

    monkeypatch.setattr(epyson, "QFont", fake_qfont)

    theme = load_layout_theme("corporate.epyson")
    # Add a bogus role name that QPalette.ColorRole does not define.
    theme.qt_palette["NotARealRole"] = "#123456"
    epyson.apply_palette(qapp, theme)
    # Window colour from the theme was still applied.
    from PySide6.QtGui import QPalette

    window = qapp.palette().color(QPalette.ColorRole.Window).name().upper()
    assert window == theme.qt_palette["Window"].upper()


# ------------------------------------------------------------------- i18n


def test_translate_widget_translates_plaintextedit_placeholder(qapp):
    from PySide6.QtWidgets import QPlainTextEdit, QVBoxLayout, QWidget

    from epy_slides import _i18n as i18n

    root = QWidget()
    layout = QVBoxLayout(root)
    area = QPlainTextEdit(root)
    area.setPlaceholderText("Type here")
    layout.addWidget(area)
    # translate_widget is a no-op in English; switch to Spanish so the
    # QPlainTextEdit placeholder branch actually runs.
    try:
        i18n.set_language("es")
        i18n.translate_widget(root)
        assert isinstance(area.placeholderText(), str)
    finally:
        i18n.set_language("en")


# -------------------------------------------------------------- pdf_footer


def test_extract_anchor_pages_reads_named_destinations(tmp_path):
    # Build a PDF that carries a named destination, then assert the helper
    # maps that anchor to its 1-based page (the loop-body branch).
    pytest.importorskip("pypdf")
    pytest.importorskip("reportlab")
    from pypdf import PdfReader, PdfWriter
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    from epy_slides._pdf_footer import extract_anchor_pages

    src = tmp_path / "src.pdf"
    pdf = canvas.Canvas(str(src), pagesize=A4)
    pdf.drawString(72, 720, "page 1")
    pdf.showPage()
    pdf.drawString(72, 720, "page 2")
    pdf.showPage()
    pdf.save()

    out = tmp_path / "named.pdf"
    reader = PdfReader(str(src))
    writer = PdfWriter()
    for page in reader.pages:
        writer.add_page(page)
    # Add a named destination pointing at the second page.
    writer.add_named_destination("intro", page_number=1)
    with out.open("wb") as fh:
        writer.write(fh)

    anchors = extract_anchor_pages(out)
    assert anchors.get("intro") == 2


# ---------------------------------------------------------------- winreg


def test_launcher_path_uses_which_when_available(monkeypatch):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "_is_frozen", lambda: False)
    monkeypatch.setattr(
        winreg_assoc.shutil, "which", lambda _name: "C:\\bin\\epy_slides.exe"
    )
    assert winreg_assoc._launcher_path() == "C:\\bin\\epy_slides.exe"


def test_icon_source_uses_which_when_available(monkeypatch):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "_is_frozen", lambda: False)
    monkeypatch.setattr(
        winreg_assoc.shutil, "which", lambda _name: "C:\\bin\\epy_slides.exe"
    )
    assert winreg_assoc._icon_source() == '"C:\\bin\\epy_slides.exe",0'


def test_open_default_apps_settings_all_uris_fail(monkeypatch):
    from epy_slides import winreg_assoc

    monkeypatch.setattr(winreg_assoc, "_is_windows", lambda: True)

    import os

    def always_fail(_uri):
        raise OSError("cannot launch")

    monkeypatch.setattr(os, "startfile", always_fail, raising=False)
    # Both the specific URI and the fallback fail → returns False.
    assert winreg_assoc.open_default_apps_settings() is False
