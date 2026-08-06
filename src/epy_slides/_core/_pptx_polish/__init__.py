"""Post-process a Pandoc-generated ``.pptx`` so text fits its frame.

Pandoc's pptx writer emits every placeholder with an empty
``<a:bodyPr/>`` — no autofit — so a dense slide silently overflows the
frame in PowerPoint. This module rewrites each slide after the
conversion:

* every content/title placeholder gets ``<a:normAutofit/>`` ("shrink
  text on overflow"), so PowerPoint keeps the text inside the frame on
  any later edit; and
* when the text measurably overflows the frame it inherits from the
  layout/master, a computed ``fontScale`` (and ``lnSpcReduction`` for
  heavy overflow) is stored so the deck opens already fitting — Office
  only recalculates autofit when a shape is edited, not on open.

Geometry and font sizes are resolved through the OOXML inheritance
chain (slide -> layout -> master text styles), so the estimate follows
whatever reference deck produced the file. Only the standard library is
used (``zipfile`` + ``xml.etree``): python-pptx stays a build-time
dependency.
"""

from __future__ import annotations

import math
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

_A = "http://schemas.openxmlformats.org/drawingml/2006/main"
_P = "http://schemas.openxmlformats.org/presentationml/2006/main"
_NS = {"a": _A, "p": _P}

_EMU_PER_PT = 12700
# Average glyph advance as a fraction of the font size. Calibrated for
# Calibri-class faces; intentionally slightly wide so the estimate errs
# toward shrinking a little rather than overflowing.
_AVG_CHAR_WIDTH = 0.52
# Single-space line height as a multiple of the font size.
_LINE_SPACING = 1.22
# Default bodyPr insets (EMU) when the shape declares none.
_INSET_LR = 91440
_INSET_TB = 45720
# Autofit floor: below this the text is unreadable; PowerPoint's own
# autofit bottoms out around 25 %, we stop earlier.
_MIN_SCALE = 0.40

# Placeholder types that never receive autofit (chrome, not content).
_SKIP_PH_TYPES = {"dt", "ftr", "sldNum"}


def _q(prefix: str, tag: str) -> str:
    return f"{{{_NS[prefix]}}}{tag}"


def _ph_key(sp: ET.Element) -> tuple[str, str] | None:
    """Return the placeholder (type, idx) key of a shape, or None."""
    ph = sp.find(f"./{_q('p', 'nvSpPr')}/{_q('p', 'nvPr')}/{_q('p', 'ph')}")
    if ph is None:
        return None
    return (ph.get("type") or "body", ph.get("idx") or "")


def _shape_frame(sp: ET.Element) -> tuple[int, int] | None:
    """Return (cx, cy) of the shape's own frame, when it declares one."""
    ext = sp.find(f"./{_q('p', 'spPr')}/{_q('a', 'xfrm')}/{_q('a', 'ext')}")
    if ext is None:
        return None
    try:
        cx, cy = int(ext.get("cx") or 0), int(ext.get("cy") or 0)
    except ValueError:
        return None
    return (cx, cy) if cx > 0 and cy > 0 else None


_REL_LAYOUT = (
    "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    "/slideLayout"
)
_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def _slide_layout(zin: zipfile.ZipFile, slide_name: str) -> str | None:
    """Return the layout member a slide inherits from, via its rels part."""
    stem = slide_name.rsplit("/", 1)[-1]
    rels_name = f"ppt/slides/_rels/{stem}.rels"
    try:
        rels = ET.fromstring(zin.read(rels_name))
    except (KeyError, ET.ParseError):
        return None
    for rel in rels.iter(f"{{{_REL_NS}}}Relationship"):
        if rel.get("Type") == _REL_LAYOUT:
            target = rel.get("Target") or ""
            return "ppt/" + target.lstrip("./").lstrip("/").removeprefix("../")
    return None


def _frames_of(xml: bytes) -> dict[tuple[str, str], tuple[int, int]]:
    """Map placeholder (type, idx) -> (cx, cy) for one layout/master."""
    root = ET.fromstring(xml)
    frames: dict[tuple[str, str], tuple[int, int]] = {}
    for sp in root.iter(_q("p", "sp")):
        key = _ph_key(sp)
        frame = _shape_frame(sp)
        if key is not None and frame is not None:
            frames[key] = frame
    return frames


def _style_sizes(master_xml: bytes) -> dict[str, list[int]]:
    """Per-level default font sizes (pt*100) from the master text styles."""
    root = ET.fromstring(master_xml)
    styles: dict[str, list[int]] = {}
    tx = root.find(f"./{_q('p', 'txStyles')}")
    if tx is None:
        return styles
    for name in ("titleStyle", "bodyStyle", "otherStyle"):
        el = tx.find(f"./{_q('p', name)}")
        sizes: list[int] = []
        if el is not None:
            for lvl in range(1, 10):
                pr = el.find(f"./{_q('a', f'lvl{lvl}pPr')}")
                sz = None
                if pr is not None:
                    rpr = pr.find(f"./{_q('a', 'defRPr')}")
                    if rpr is not None and rpr.get("sz"):
                        sz = int(rpr.get("sz"))  # type: ignore[arg-type]
                sizes.append(sz if sz else (sizes[-1] if sizes else 1800))
        styles[name] = sizes or [1800] * 9
    return styles


def _para_level(p: ET.Element) -> int:
    pr = p.find(f"./{_q('a', 'pPr')}")
    if pr is not None and pr.get("lvl"):
        try:
            return int(pr.get("lvl"))  # type: ignore[arg-type]
        except ValueError:
            return 0
    return 0


def _para_text_and_size(
    p: ET.Element, level_sizes: list[int], level: int
) -> tuple[str, int]:
    """Concatenated run text and the paragraph's effective font size."""
    default = level_sizes[min(level, len(level_sizes) - 1)]
    size = default
    chunks: list[str] = []
    for r in p.findall(f"./{_q('a', 'r')}"):
        rpr = r.find(f"./{_q('a', 'rPr')}")
        if rpr is not None and rpr.get("sz"):
            try:
                size = int(rpr.get("sz"))  # type: ignore[arg-type]
            except ValueError:
                size = default
        t = r.find(f"./{_q('a', 't')}")
        if t is not None and t.text:
            chunks.append(t.text)
    return "".join(chunks), size


def _estimate_scale(
    tx_body: ET.Element, frame: tuple[int, int], level_sizes: list[int]
) -> float:
    """Estimated fit ratio (>= 1.0 means the text already fits)."""
    cx, cy = frame
    usable_cx = max(cx - 2 * _INSET_LR, 1)
    usable_cy = max(cy - 2 * _INSET_TB, 1)
    height = 0.0
    for p in tx_body.findall(f"./{_q('a', 'p')}"):
        level = _para_level(p)
        text, sz = _para_text_and_size(p, level_sizes, level)
        size_emu = (sz / 100.0) * _EMU_PER_PT
        # Bullet indent narrows the wrap column at deeper levels.
        wrap_cx = max(usable_cx - level * int(0.35 * 914400), 1)
        text_emu = len(text) * size_emu * _AVG_CHAR_WIDTH
        lines = max(1, math.ceil(text_emu / wrap_cx))
        height += lines * size_emu * _LINE_SPACING
    if height <= 0:
        return 1.0
    return usable_cy / height


def _apply_autofit(sp: ET.Element, scale: float) -> None:
    """Write ``<a:normAutofit/>`` (with fontScale when needed) on a shape."""
    tx_body = sp.find(f"./{_q('p', 'txBody')}")
    if tx_body is None:
        return
    body_pr = tx_body.find(f"./{_q('a', 'bodyPr')}")
    if body_pr is None:
        body_pr = ET.Element(_q("a", "bodyPr"))
        tx_body.insert(0, body_pr)
    for tag in ("normAutofit", "spAutoFit", "noAutofit"):
        for old in body_pr.findall(f"./{_q('a', tag)}"):
            body_pr.remove(old)
    autofit = ET.SubElement(body_pr, _q("a", "normAutofit"))
    if scale < 0.98:
        clamped = max(_MIN_SCALE, scale)
        # Quantize to 5 % steps (matches what PowerPoint itself stores).
        steps = math.floor(clamped * 20) / 20
        autofit.set("fontScale", str(int(steps * 100000)))
        if steps <= 0.75:
            autofit.set("lnSpcReduction", "10000")


def polish_pptx(path: Path) -> None:
    """Fit slide text to its frame, in place (see module docstring)."""
    ET.register_namespace("a", _A)
    ET.register_namespace("p", _P)
    ET.register_namespace(
        "r", "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
    )
    with zipfile.ZipFile(path) as zin:
        names = zin.namelist()
        masters = sorted(
            n for n in names if re.fullmatch(r"ppt/slideMasters/slideMaster\d+\.xml", n)
        )
        slides = sorted(
            n for n in names if re.fullmatch(r"ppt/slides/slide\d+\.xml", n)
        )
        if not masters or not slides:
            return
        master_xml = zin.read(masters[0])
        master_frames = _frames_of(master_xml)
        # Geometry is inherited per slide: shape -> its own layout ->
        # master. A global layout merge would let one layout's title box
        # shadow every other slide's.
        layout_frames: dict[str, dict[tuple[str, str], tuple[int, int]]] = {}

        def _frames_for(slide_name: str) -> dict[tuple[str, str], tuple[int, int]]:
            layout = _slide_layout(zin, slide_name)
            if layout is None:
                return master_frames
            if layout not in layout_frames:
                merged = dict(master_frames)
                try:
                    merged.update(_frames_of(zin.read(layout)))
                except KeyError:
                    pass
                layout_frames[layout] = merged
            return layout_frames[layout]

        styles = _style_sizes(master_xml)
        replacements: dict[str, bytes] = {}
        for slide in slides:
            frames = _frames_for(slide)
            root = ET.fromstring(zin.read(slide))
            changed = False
            for sp in root.iter(_q("p", "sp")):
                key = _ph_key(sp)
                if key is None or key[0] in _SKIP_PH_TYPES:
                    continue
                tx_body = sp.find(f"./{_q('p', 'txBody')}")
                if tx_body is None:
                    continue
                frame = _shape_frame(sp) or frames.get(key)
                if frame is None and key[0] not in ("title", "ctrTitle"):
                    # Content placeholders pandoc leaves unnamed inherit
                    # the master body frame.
                    frame = frames.get(("body", "1"))
                if frame is None:
                    continue
                level_sizes = styles.get(
                    "titleStyle" if key[0] in ("title", "ctrTitle") else "bodyStyle",
                    [1800] * 9,
                )
                scale = _estimate_scale(tx_body, frame, level_sizes)
                _apply_autofit(sp, scale)
                changed = True
            if changed:
                replacements[slide] = ET.tostring(
                    root, xml_declaration=True, encoding="UTF-8"
                )
        if not replacements:
            return
        entries = [(item, zin.read(item.filename)) for item in zin.infolist()]
    tmp = path.with_suffix(".polish.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        for item, data in entries:
            zout.writestr(item, replacements.get(item.filename, data))
    tmp.replace(path)
