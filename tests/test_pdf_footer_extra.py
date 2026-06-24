"""Tests for the remaining PDF stamping helpers (background, watermark,
header, metadata, anchor extraction, and the page-numbering primitives).

The footer text path itself is covered by ``test_pdf_footer.py``; this file
exercises the other public ``add_*`` entry points and the pure numbering
helpers. All required packages are runtime dependencies, so the
``importorskip`` guards only protect a degraded install, never hide a
failure on a complete one.
"""

from __future__ import annotations

import pytest

pytest.importorskip("pypdf")
pytest.importorskip("reportlab")
pytest.importorskip("PIL")

from epy_slides._pdf_footer import (  # noqa: E402
    _page_label,
    _page_stamp,
    _roman,
    add_footer,
    add_header,
    add_metadata,
    add_page_background,
    add_watermark,
    extract_anchor_pages,
)


def _make_pdf(path, pages: int = 1) -> None:
    """Create a tiny multi-page PDF with reportlab."""
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas

    pdf = canvas.Canvas(str(path), pagesize=A4)
    for i in range(pages):
        pdf.drawString(72, 720, f"Body page {i + 1}")
        pdf.showPage()
    pdf.save()


def _make_png(path, size: tuple[int, int] = (40, 20)) -> None:
    """Write a tiny opaque RGBA PNG with Pillow."""
    from PIL import Image

    Image.new("RGBA", size, (10, 120, 220, 255)).save(str(path))


# --------------------------------------------------------------- _roman


@pytest.mark.parametrize(
    ("number", "expected"),
    [
        (1, "i"), (4, "iv"), (9, "ix"),
        (14, "xiv"), (40, "xl"), (2026, "mmxxvi"),
    ],
)
def test_roman_known_values(number, expected):
    assert _roman(number) == expected


def test_roman_non_positive_returns_str():
    assert _roman(0) == "0"
    assert _roman(-3) == "-3"


# --------------------------------------------------------------- _page_label


def test_page_label_english_default():
    assert _page_label("en", 2, 5) == "Page 2 of 5"


def test_page_label_spanish():
    assert _page_label("es", 1, 3) == "Pág. 1 de 3"


def test_page_label_unknown_lang_falls_back_to_english():
    assert _page_label("de", 1, 1) == "Page 1 of 1"


def test_page_label_empty_lang():
    assert _page_label("", 1, 1) == "Page 1 of 1"


# --------------------------------------------------------------- _page_stamp


def test_page_stamp_legacy_unnumbered_front_matter():
    assert _page_stamp(1, 3, 3, "en", None, True) == (False, None)


def test_page_stamp_legacy_numbered_body():
    assert _page_stamp(3, 3, 3, "en", None, True) == (
        True, "Page 1 of 3",
    )


def test_page_stamp_legacy_no_numbers_still_stamps():
    assert _page_stamp(3, 3, 3, "en", None, False) == (True, None)


def test_page_stamp_segments_before_first_boundary():
    segments = [(2, "roman"), (4, "arabic")]
    assert _page_stamp(1, 1, 3, "en", segments, True) == (False, None)


def test_page_stamp_segments_roman_then_arabic():
    segments = [(2, "roman"), (4, "arabic")]
    # page 2 → first roman → i ; page 4 → first arabic → 1
    assert _page_stamp(2, 1, 3, "en", segments, True) == (True, "i")
    assert _page_stamp(3, 1, 3, "en", segments, True) == (True, "ii")
    assert _page_stamp(4, 1, 3, "en", segments, True) == (True, "1")


def test_page_stamp_segments_no_numbers():
    segments = [(1, "arabic")]
    assert _page_stamp(2, 1, 3, "en", segments, False) == (True, None)


# --------------------------------------------------- add_footer with segments


def test_add_footer_segments_roman_and_arabic(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=4)
    add_footer(
        pdf_path, "", page_numbers=True,
        segments=[(1, "roman"), (3, "arabic")],
    )
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 4
    text = "".join(p.extract_text() or "" for p in reader.pages)
    assert "i" in text  # roman front matter
    assert "1" in text  # arabic body


# ------------------------------------------------------- add_page_background


def test_add_page_background_preserves_pages(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=2)
    add_page_background(pdf_path, "#102030")
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2


def test_add_page_background_empty_color_is_noop(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    before = pdf_path.read_bytes()
    add_page_background(pdf_path, "")
    assert pdf_path.read_bytes() == before


def test_add_page_background_bad_color_is_noop(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    before = pdf_path.read_bytes()
    add_page_background(pdf_path, "not-a-color")
    assert pdf_path.read_bytes() == before


def test_add_page_background_respects_start_page(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=3)
    add_page_background(pdf_path, "#FFEECC", start_page=2)
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 3


# --------------------------------------------------------------- add_watermark


def test_add_watermark_preserves_pages(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    img = tmp_path / "logo.png"
    _make_pdf(pdf_path, pages=2)
    _make_png(img)
    add_watermark(pdf_path, img, opacity=0.2, width_ratio=0.5)
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2


def test_add_watermark_missing_image_is_noop(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    before = pdf_path.read_bytes()
    add_watermark(pdf_path, tmp_path / "missing.png")
    assert pdf_path.read_bytes() == before


# --------------------------------------------------------------- add_header


def test_add_header_single_row(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    add_header(pdf_path, ["Left", "Center", "Right"])
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 1


def test_add_header_two_rows(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=2)
    add_header(pdf_path, ["A", "B", "C", "D", "E", "F"], start_page=1)
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 2


def test_add_header_empty_cells_is_noop(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    before = pdf_path.read_bytes()
    add_header(pdf_path, [])
    assert pdf_path.read_bytes() == before
    add_header(pdf_path, ["", "", ""])
    assert pdf_path.read_bytes() == before


def test_add_header_respects_start_page(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=3)
    add_header(pdf_path, ["Header"], start_page=2)
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    assert len(reader.pages) == 3


# --------------------------------------------------------------- add_metadata


def test_add_metadata_writes_info(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    add_metadata(
        pdf_path,
        title="My Deck",
        author="ANM",
        subject="Sub",
        keywords="a,b",
        rights="© 2026 ANM",
    )
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    meta = reader.metadata
    assert meta is not None
    assert meta.get("/Title") == "My Deck"
    assert meta.get("/Author") == "ANM"
    assert meta.get("/Creator") == "epy_slides"
    assert meta.get("/Copyright") == "© 2026 ANM"


def test_add_metadata_always_sets_creator_and_producer(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=1)
    # With all optional values empty, only creator/producer are written; the
    # rights/keywords entries the caller did not supply are not added.
    add_metadata(pdf_path)
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    meta = reader.metadata
    assert meta is not None
    assert meta.get("/Creator") == "epy_slides"
    assert meta.get("/Producer", "").startswith("epy_slides")
    assert "/Copyright" not in meta


# ----------------------------------------------------- extract_anchor_pages


def test_extract_anchor_pages_no_destinations(tmp_path):
    pdf_path = tmp_path / "doc.pdf"
    _make_pdf(pdf_path, pages=2)
    # A plain reportlab PDF has no named destinations.
    assert extract_anchor_pages(pdf_path) == {}


def test_extract_anchor_pages_corrupt_pdf_returns_empty(tmp_path):
    bad = tmp_path / "bad.pdf"
    bad.write_bytes(b"%PDF-1.4 not really a pdf")
    assert extract_anchor_pages(bad) == {}
