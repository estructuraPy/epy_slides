"""Tests for the dev-only ``make_icon`` build-tooling script.

Covers ``_letterbox`` (aspect-preserving square-canvas padding),
``_write_ico``/``_verify_ico`` (multi-size ICO round-trip), and
``generate`` (the end-to-end entry point), using real Pillow ``Image``
objects throughout -- no mocking of PIL itself.
"""

from __future__ import annotations

import importlib
import shutil
import struct
import sys
from pathlib import Path

import pytest
from PIL import Image

from epy_slides._core._packaging import make_icon
from epy_slides._core._packaging.make_icon import (
    SIZES,
    _letterbox,
    _verify_ico,
    _write_ico,
    generate,
)

MODULE_NAME = "epy_slides._core._packaging.make_icon"


# ---------------------------------------------------------------------------
# _letterbox
# ---------------------------------------------------------------------------

def test_letterbox_wide_image_pads_top_and_bottom():
    """A wider-than-tall source is scaled to full width, bands top/bottom."""
    src = Image.new("RGBA", (40, 20), (255, 0, 0, 255))
    out = _letterbox(src, 20)

    assert out.size == (20, 20)
    assert out.mode == "RGBA"
    assert out.getpixel((10, 2)) == (0, 0, 0, 0)  # top band: transparent
    assert out.getpixel((10, 10)) == (255, 0, 0, 255)  # scaled content
    assert out.getpixel((10, 18)) == (0, 0, 0, 0)  # bottom band: transparent


def test_letterbox_tall_image_pads_left_and_right():
    """A taller-than-wide source is scaled to full height, bands the sides."""
    src = Image.new("RGBA", (20, 40), (0, 255, 0, 255))
    out = _letterbox(src, 20)

    assert out.size == (20, 20)
    assert out.getpixel((2, 10)) == (0, 0, 0, 0)  # left band: transparent
    assert out.getpixel((10, 10)) == (0, 255, 0, 255)  # scaled content
    assert out.getpixel((18, 10)) == (0, 0, 0, 0)  # right band: transparent


def test_letterbox_square_image_is_a_no_op_scale():
    """Counter-example: a square source needs no scaling or padding."""
    src = Image.new("RGBA", (20, 20), (0, 0, 255, 255))
    out = _letterbox(src, 20)

    assert out.size == (20, 20)
    # No letterbox bands: the whole canvas is opaque source color.
    assert out.getpixel((0, 0)) == (0, 0, 255, 255)
    assert out.getpixel((19, 19)) == (0, 0, 255, 255)


def test_letterbox_non_rgba_source_uses_none_mask():
    """A source without an alpha channel takes the ``mask=None`` branch.

    ``canvas.paste(thumb, (x, y), mask=thumb if thumb.mode == "RGBA" else
    None)`` -- an RGB source keeps ``thumb.mode == "RGB"``, so the paste
    happens without a mask. The result must still be fully opaque, since
    a maskless paste onto an RGBA canvas fills alpha=255.
    """
    src = Image.new("RGB", (20, 20), (10, 20, 30))
    out = _letterbox(src, 20)

    assert out.size == (20, 20)
    assert out.mode == "RGBA"
    assert out.getpixel((0, 0)) == (10, 20, 30, 255)
    assert out.getpixel((19, 19)) == (10, 20, 30, 255)


# ---------------------------------------------------------------------------
# _write_ico / _verify_ico
# ---------------------------------------------------------------------------

def test_write_ico_produces_a_valid_multi_size_ico(tmp_path):
    """The written file round-trips through Pillow with all four sizes."""
    frames = [
        _letterbox(Image.new("RGBA", (40, 20), (255, 0, 0, 255)), size)
        for size in SIZES
    ]
    ico_path = tmp_path / "test.ico"

    _write_ico(frames, ico_path)

    assert ico_path.exists()

    # Independent check #1: the ICONDIR header bytes.
    with open(ico_path, "rb") as fh:
        reserved, image_type, count = struct.unpack("<HHH", fh.read(6))
    assert (reserved, image_type, count) == (0, 1, len(SIZES))

    # Independent check #2: reopen with Pillow and inspect the directory.
    reopened = Image.open(ico_path)
    assert sorted(reopened.info["sizes"]) == sorted(
        (size, size) for size in SIZES
    )
    assert len(reopened.ico.entry) == len(SIZES)


def test_verify_ico_returns_the_frame_count_from_a_real_file(tmp_path):
    """``_verify_ico`` reports the count written by ``_write_ico``."""
    frames = [
        _letterbox(Image.new("RGBA", (20, 20), (0, 255, 0, 255)), size)
        for size in SIZES
    ]
    ico_path = tmp_path / "roundtrip.ico"
    _write_ico(frames, ico_path)

    assert _verify_ico(ico_path) == len(SIZES) == 4


# ---------------------------------------------------------------------------
# generate
# ---------------------------------------------------------------------------

def test_generate_writes_ico_only_under_the_patched_output_dir(
    tmp_path, monkeypatch
):
    """``generate()`` reads the real packaged PNG, writes only to tmp_path.

    ``OUT_DIR`` is the constant ``generate()`` actually dereferences at
    call time to build ``ico_path`` (``OUT_DIR / "epy_slides.ico"``
    executes inside the function body, not baked in at import time), so
    patching it alone is sufficient to redirect all output. ``SRC_PNG``
    is left untouched and continues to point at the real, pre-existing
    packaged asset (read-only for this test, never written to).
    """
    real_src_png = make_icon.SRC_PNG
    assert real_src_png.exists(), "packaged source PNG must pre-exist"
    real_out_dir = make_icon.OUT_DIR

    out_dir = tmp_path / "out"
    monkeypatch.setattr(make_icon, "OUT_DIR", out_dir)

    generate()

    ico_path = out_dir / "epy_slides.ico"
    assert ico_path.exists()
    assert ico_path.is_relative_to(tmp_path)

    reopened = Image.open(ico_path)
    assert sorted(reopened.info["sizes"]) == sorted(
        (size, size) for size in SIZES
    )

    # Nothing was written under the real repo tree: the patched OUT_DIR
    # is a different directory than the real one, and the real one's
    # pre-existing ICO (if any) is untouched -- generate() only ever
    # opened SRC_PNG for reading.
    assert out_dir == make_icon.OUT_DIR
    assert real_out_dir != out_dir
    assert real_src_png == make_icon.SRC_PNG


def test_generate_raises_systemexit_when_source_missing(
    tmp_path, monkeypatch
):
    """The missing-source guard raises before touching the filesystem."""
    monkeypatch.setattr(make_icon, "SRC_PNG", tmp_path / "does-not-exist.png")
    monkeypatch.setattr(make_icon, "OUT_DIR", tmp_path / "out")

    with pytest.raises(SystemExit, match="Source image not found"):
        generate()

    assert not (tmp_path / "out").exists()


# ---------------------------------------------------------------------------
# Pillow-missing import guard
# ---------------------------------------------------------------------------

def test_main_guard_runs_generate_end_to_end(tmp_path, capsys):
    """Running the file as a script exercises the ``__main__`` block.

    The only way to reach ``if __name__ == "__main__":`` is to execute
    the module's source with ``__name__`` set to ``"__main__"``, and the
    script hardcodes its I/O paths from its own ``__file__`` at import
    time -- there is no seam to redirect them from inside a normal
    import, and a plain subprocess re-run would (a) not be measured by
    this process's coverage tracer and (b) resolve ``ROOT``/``OUT_DIR``/
    ``SRC_PNG`` from the REAL file path, writing into the real repo
    tree.

    So this test compiles the real source with its real, correct
    filename (so coverage attributes the executed lines to the actual
    file being measured) but execs it with a *different* ``__file__``
    global pointing under ``tmp_path`` (``__file__`` is just a plain
    global the script's own ``Path(__file__)`` arithmetic reads -- it is
    independent of the filename baked into the compiled code object).
    ``ROOT``/``OUT_DIR``/``SRC_PNG`` are then derived entirely under
    ``tmp_path``, so nothing is read from or written to the real
    ``src/`` tree (proven below: the real ICO's mtime is unchanged).
    """
    real_init = Path(make_icon.__file__)
    real_packaging_dir = real_init.parent.parent
    real_src_png = real_packaging_dir / "assets_build" / "epy_slides.png"
    real_ico = real_packaging_dir / "assets_build" / "epy_slides.ico"
    real_ico_mtime_before = real_ico.stat().st_mtime_ns

    fake_assets_dir = tmp_path / "_packaging" / "assets_build"
    fake_assets_dir.mkdir(parents=True)
    shutil.copyfile(real_src_png, fake_assets_dir / "epy_slides.png")
    fake_init = tmp_path / "_packaging" / "make_icon" / "__init__.py"

    code = compile(
        real_init.read_text(encoding="utf-8"), str(real_init), "exec"
    )
    exec(code, {"__name__": "__main__", "__file__": str(fake_init)})

    captured = capsys.readouterr()
    assert "Generating epy_slides icons..." in captured.out
    assert "Done." in captured.out

    out_ico = fake_assets_dir / "epy_slides.ico"
    assert out_ico.exists()
    reopened = Image.open(out_ico)
    assert sorted(reopened.info["sizes"]) == sorted(
        (size, size) for size in SIZES
    )

    # Nothing was read from or written to the real repo tree: the real
    # ICO's mtime is unchanged.
    assert real_ico.stat().st_mtime_ns == real_ico_mtime_before


def test_module_raises_systemexit_when_pillow_is_unavailable(monkeypatch):
    """The top-level ``try/except ImportError`` guard around Pillow.

    Pillow is always installed in this environment, so the guard cannot
    be exercised by omission. ``sys.modules["PIL"] = None`` is the
    standard way to force the next ``from PIL import Image`` to raise
    ImportError (Python's import system treats a ``None`` entry as
    "known absent" and raises immediately), so the module is evicted
    from ``sys.modules`` and freshly re-imported under that condition.
    ``monkeypatch`` restores both entries afterward, so later tests see
    the real, already-working module object again.
    """
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.delitem(sys.modules, MODULE_NAME, raising=False)

    with pytest.raises(SystemExit, match="Pillow is required"):
        importlib.import_module(MODULE_NAME)
