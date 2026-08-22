"""Tests for the interactive-Plotly wiring in epy_slides.

Covers the fenced-block expansion (:mod:`epy_slides._core._plotly`), the
reveal.js bundle/init injection (:func:`build_reveal_document`) and the
PPTX degrade path (:func:`expand_for_pptx`).
"""

from __future__ import annotations

# plotly is NOT a runtime dependency of epy_slides: _core._plotly
# duck-types on ``.to_json()`` and never imports it. It IS a declared
# test dependency (the dev extra), because the contract below is only
# meaningful against the real library.
import plotly.graph_objects as go

from epy_slides._core._plotly import (
    figure_to_markdown,
    strip_plotly_for_export,
    uses_plotly,
)
from epy_slides._core.slide_md import expand_for_pptx, expand_for_revealjs
from epy_slides._core.template import build_reveal_document


class _FakeFig:
    """A minimal duck-typed figure — no plotly install needed."""

    def to_json(self):
        return '{"data": [{"type": "scatter", "y": [1, 2, 3]}], "layout": {}}'


def test_figure_to_markdown_detected_by_uses_plotly():
    """The emitted fence is recognised by the renderer's detector."""
    assert uses_plotly(figure_to_markdown(_FakeFig()))


def test_expand_for_revealjs_makes_interactive_div():
    """A plotly fence becomes a live div + JSON script in a reveal deck."""
    md = figure_to_markdown(
        _FakeFig(), fallback="figs/twin.png", height="360px"
    )
    out = expand_for_revealjs(md)
    assert 'class="epy-plotly"' in out
    assert 'data-plotly-for="epy-plotly-0"' in out
    assert 'style="height: 360px;"' in out
    assert '"type": "scatter"' in out


def test_expand_for_pptx_degrades_to_fallback_image():
    """PowerPoint has no Plotly renderer, so the fence becomes the raster."""
    md = figure_to_markdown(_FakeFig(), fallback="figs/twin.png")
    out = expand_for_pptx(md)
    assert "![](figs/twin.png)" in out
    assert "epy-plotly" not in out


def test_strip_plotly_for_export_uses_fallback():
    """The static export helper substitutes the declared fallback image."""
    md = figure_to_markdown(_FakeFig(), fallback="figs/twin.png")
    assert "![](figs/twin.png)" in strip_plotly_for_export(md)


def test_build_reveal_document_injects_bundle_and_init_when_plotly():
    """With ``plotly=True`` the deck carries the engine, init and resize."""
    doc = build_reveal_document(
        body="<section>x</section>", base_dir=None, title="t", plotly=True,
    )
    assert "window._epy_init_plotly" in doc
    assert "Plotly.newPlot" in doc
    assert "window._epy_resize_plotly" in doc
    assert (
        "deck.on('slidechanged', function () "
        "{ window._epy_resize_plotly(); });"
    ) in doc


def test_build_reveal_document_omits_plotly_when_absent():
    """The ~3.5 MB bundle is inlined only when the deck uses a figure."""
    with_p = build_reveal_document(
        body="<section>x</section>", base_dir=None, title="t", plotly=True,
    )
    without = build_reveal_document(
        body="<section>x</section>", base_dir=None, title="t", plotly=False,
    )
    assert "_epy_init_plotly" not in without
    assert "_epy_resize_plotly" not in without
    assert (len(with_p) - len(without)) > 3_000_000


def test_real_plotly_figure_roundtrips_into_revealjs():
    """A real Plotly figure serializes and expands into a reveal div."""
    fig = go.Figure(go.Scatter(y=[1, 2, 3]))
    out = expand_for_revealjs(figure_to_markdown(fig))
    assert 'class="epy-plotly"' in out
    assert "scatter" in out.lower()
