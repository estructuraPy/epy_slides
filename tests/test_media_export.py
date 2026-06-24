"""Tests for diagram collection / substitution used by the PPTX export.

The :func:`render_diagram_pngs` rasteriser needs a running Qt WebEngine and
is exercised indirectly elsewhere; here we test the pure helpers: diagram
collection, the offscreen page HTML builder and the source substitution.
"""

from __future__ import annotations

from pathlib import Path

from epy_slides._media_export import (
    _diagram_page_html,
    collect_diagrams,
    render_diagram_pngs,
    substitute_diagram_images,
)

# ----------------------------------------------------------- collect_diagrams


def test_collect_diagrams_orders_mermaid_and_nomnoml():
    source = (
        "Intro\n"
        "```mermaid\nflowchart LR\nA-->B\n```\n"
        "Middle\n"
        "```nomnoml\n[A]->[B]\n```\n"
    )
    diagrams = collect_diagrams(source)
    assert [engine for engine, _ in diagrams] == ["mermaid", "nomnoml"]
    assert "flowchart LR" in diagrams[0][1]
    assert "[A]->[B]" in diagrams[1][1]


def test_collect_diagrams_handles_attribute_fence():
    source = "```{.mermaid}\ngraph TD\nA-->B\n```\n"
    diagrams = collect_diagrams(source)
    assert len(diagrams) == 1
    assert diagrams[0][0] == "mermaid"


def test_collect_diagrams_ignores_other_languages():
    source = "```python\nprint('hi')\n```\n"
    assert collect_diagrams(source) == []


def test_collect_diagrams_empty_source():
    assert collect_diagrams("") == []


# --------------------------------------------------------- _diagram_page_html


def test_diagram_page_html_escapes_body_and_includes_theme():
    diagrams = [("nomnoml", "[A & B]\n<x>")]
    html = _diagram_page_html(diagrams, theme_css=":root{--epy-bg:#fff;}")
    assert "&amp;" in html
    assert "&lt;x&gt;" in html
    assert "--epy-bg:#fff" in html
    assert 'class="nomnoml"' in html


def test_diagram_page_html_only_loads_used_engines():
    html = _diagram_page_html([("nomnoml", "[A]->[B]")], theme_css="")
    assert "_epy_init_nomnoml" in html
    assert "_epy_init_mermaid()" not in html


def test_diagram_page_html_loads_mermaid_engine():
    # A mermaid diagram drives the mermaid head/init branch.
    html = _diagram_page_html(
        [("mermaid", "flowchart LR\nA-->B")], theme_css=""
    )
    assert "_epy_init_mermaid()" in html
    assert 'class="mermaid"' in html


def test_diagram_page_html_loads_both_engines():
    html = _diagram_page_html(
        [("mermaid", "graph TD\nA-->B"), ("nomnoml", "[A]->[B]")],
        theme_css="",
    )
    assert "_epy_init_mermaid()" in html
    assert "_epy_init_nomnoml" in html


# --------------------------------------------------- substitute_diagram_images


def test_substitute_replaces_each_fence_with_image_link():
    source = (
        "```mermaid\nA-->B\n```\n"
        "```nomnoml\n[A]->[B]\n```\n"
    )
    pngs: list[Path | None] = [Path("d0.png"), Path("d1.png")]
    out = substitute_diagram_images(source, pngs)
    assert "![](d0.png)" in out
    assert "![](d1.png)" in out
    assert "```mermaid" not in out


def test_substitute_keeps_source_when_png_is_none():
    source = "```mermaid\nA-->B\n```\n"
    out = substitute_diagram_images(source, [None])
    assert "```mermaid" in out
    assert "![]" not in out


def test_substitute_keeps_source_when_png_list_short():
    source = "```mermaid\nA-->B\n```\n"
    out = substitute_diagram_images(source, [])
    assert "```mermaid" in out


# ------------------------------------------------- render_diagram_pngs guards


def test_render_diagram_pngs_empty_returns_empty(tmp_path):
    assert render_diagram_pngs([], tmp_path) == []


def test_render_diagram_pngs_without_qapp_returns_none(tmp_path, monkeypatch):
    # With no running QApplication the rasteriser must return None per
    # diagram so the export falls back to source text.
    from PySide6 import QtWidgets

    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: None)
    )
    out = render_diagram_pngs(
        [("mermaid", "A-->B"), ("nomnoml", "[A]")], tmp_path
    )
    assert out == [None, None]


# ------------------------------------ render_diagram_pngs full (mocked Qt)


class _FakeSignal:
    """Minimal Qt-signal stand-in storing the connected slot."""

    def __init__(self):
        self.slot = None

    def connect(self, slot, *a, **k):
        self.slot = slot


class _FakePixmap:
    """Fake QPixmap whose copy/save succeed for the cropping path."""

    def __init__(self, w=1400, saved=None):
        self._w = w
        self._saved = [] if saved is None else saved

    def width(self):
        return self._w

    def copy(self, _rect):
        return self

    def save(self, path):
        self._saved.append(path)
        return True


class _FakePage:
    """Fake page: load fires immediately; JS returns ready and the rects."""

    def __init__(self, rects_json):
        self._rects = rects_json

    def runJavaScript(self, expr, callback):  # noqa: N802
        if "_md === true" in expr:
            callback(True)
        else:
            callback(self._rects)


class _FakeView:
    """Fake QWebEngineView returning a fake pixmap and a fake page."""

    def __init__(self, rects_json, pix):
        self.loadFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._page = _FakePage(rects_json)
        self._pix = pix

    def setAttribute(self, *a, **k):  # noqa: N802
        pass

    def resize(self, *a):
        pass

    def show(self):
        pass

    def width(self):
        return 1400

    def page(self):
        return self._page

    def load(self, _url):
        if self.loadFinished.slot is not None:
            self.loadFinished.slot(True)

    def grab(self):
        return self._pix

    def deleteLater(self):  # noqa: N802
        pass


class _FakeApp:
    def processEvents(self, *a, **k):  # noqa: N802
        pass


def test_render_diagram_pngs_crops_and_saves(tmp_path, monkeypatch):
    # Drive the full render path with a mocked Qt boundary: two diagrams,
    # both with valid bounding rects, are cropped from one grab and saved.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    rects = "[[0,0,200,150],[210,0,200,150]]"
    pix = _FakePixmap()
    view = _FakeView(rects, pix)
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    diagrams = [("mermaid", "A-->B"), ("nomnoml", "[A]->[B]")]
    out = render_diagram_pngs(diagrams, tmp_path, theme_css=":root{}")
    assert out[0] == tmp_path / "diagram_0.png"
    assert out[1] == tmp_path / "diagram_1.png"


def test_render_diagram_pngs_skips_tiny_rects(tmp_path, monkeypatch):
    # A degenerate (<2px) rect is skipped, leaving None for that diagram.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    rects = "[[0,0,0,0]]"
    view = _FakeView(rects, _FakePixmap())
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    out = render_diagram_pngs([("mermaid", "A")], tmp_path)
    assert out == [None]


def test_render_diagram_pngs_handles_non_string_rects(tmp_path, monkeypatch):
    # When the rects probe returns a non-string the JSON parse is skipped
    # (rects = []) and every diagram falls back to None.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    view = _FakeView(0, _FakePixmap())
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    out = render_diagram_pngs([("mermaid", "A")], tmp_path)
    assert out == [None]


def test_render_diagram_pngs_ignores_extra_rects(tmp_path, monkeypatch):
    # More rects than diagrams: the loop breaks once it passes the diagram
    # count, so only the first diagram is rendered.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    rects = "[[0,0,200,150],[210,0,200,150]]"
    view = _FakeView(rects, _FakePixmap())
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    out = render_diagram_pngs([("mermaid", "A")], tmp_path)
    assert out[0] == tmp_path / "diagram_0.png"
    assert len(out) == 1


class _DeferredApp:
    """Fake app whose processEvents drains one queued action at a time."""

    def __init__(self):
        self.queue = []

    def processEvents(self, *a, **k):  # noqa: N802
        if self.queue:
            self.queue.pop(0)()


class _DeferredPage:
    """Page that defers its JS results so the poll-loop bodies execute."""

    def __init__(self, app, rects_json):
        self.app = app
        self._rects = rects_json
        self._md_calls = 0

    def runJavaScript(self, expr, callback):  # noqa: N802
        if "_md === true" in expr:
            self._md_calls += 1
            value = self._md_calls >= 2
        else:
            value = self._rects
        self.app.queue.append(lambda: callback(value))


class _DeferredView:
    """View that defers loadFinished so the load-wait loop body runs."""

    def __init__(self, app, rects_json, pix):
        self.app = app
        self.loadFinished = _FakeSignal()  # noqa: N815 (Qt name)
        self._page = _DeferredPage(app, rects_json)
        self._pix = pix

    def setAttribute(self, *a, **k):  # noqa: N802
        pass

    def resize(self, *a):
        pass

    def show(self):
        pass

    def width(self):
        return 1400

    def page(self):
        return self._page

    def load(self, _url):
        self.app.queue.append(
            lambda: self.loadFinished.slot
            and self.loadFinished.slot(True)
        )

    def grab(self):
        return self._pix

    def deleteLater(self):  # noqa: N802
        pass


def test_render_diagram_pngs_drives_poll_loops(tmp_path, monkeypatch):
    # Drive the async poll loops: the deferred view resolves load/JS only on
    # processEvents, so the load-wait, _md-wait and js() loop bodies all run.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    app = _DeferredApp()
    view = _DeferredView(app, "[[0,0,200,150]]", _FakePixmap())
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: app)
    )
    out = render_diagram_pngs([("mermaid", "A")], tmp_path)
    assert out[0] == tmp_path / "diagram_0.png"


def test_render_diagram_pngs_without_pyside_returns_none(
    tmp_path, monkeypatch
):
    # If the PySide6 imports inside the function fail, the rasteriser returns
    # None per diagram (the ImportError env guard).
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("PySide6"):
            raise ImportError("no PySide6")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    out = render_diagram_pngs([("mermaid", "A"), ("nomnoml", "[B]")], tmp_path)
    assert out == [None, None]


def test_render_diagram_pngs_handles_grab_error(tmp_path, monkeypatch):
    # A RuntimeError mid-render is swallowed; the result stays all-None.
    from PySide6 import QtWebEngineWidgets, QtWidgets

    class _BoomView(_FakeView):
        def grab(self):
            raise RuntimeError("offscreen grab failed")

    view = _BoomView("[[0,0,200,150]]", _FakePixmap())
    monkeypatch.setattr(
        QtWebEngineWidgets, "QWebEngineView", lambda *a, **k: view
    )
    monkeypatch.setattr(
        QtWidgets.QApplication, "instance", staticmethod(lambda: _FakeApp())
    )
    out = render_diagram_pngs([("mermaid", "A")], tmp_path)
    assert out == [None]
