"""The second renderer, reachable from ePy Slides.

ePy Docs builds reports, papers, books and notebooks -- not decks. What
this offers is the deck's CONTENT as a document: the handout, not the
presentation. It is the second of the two rendering options this editor
has, and it sits after a separator for that reason.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from epy_export import APPEARANCES, DOCUMENT_TYPES, RenderOptions
from epy_export._core import _backends

from epy_slides.epy_suite_connect._adapters import docs_bridge


class _Blocker:
    """Makes ``epy_docs`` genuinely unimportable, as a bundle does."""

    def find_spec(self, name, path=None, target=None):  # noqa: ANN001, ANN201
        if name == "epy_docs" or name.startswith("epy_docs."):
            raise ImportError("epy_docs is not importable in this process")
        return None


@pytest.fixture()
def engine_hidden():
    """Hide the engine from every import in this process.

    Reporting it absent is not enough: it IS installed on the machine
    these tests run on, so a bridge that asked its own import path would
    answer correctly here and wrongly in every frozen bundle.
    """
    saved = sys.modules.pop("epy_docs", None)
    blocker = _Blocker()
    sys.meta_path.insert(0, blocker)
    try:
        yield
    finally:
        sys.meta_path.remove(blocker)
        if saved is not None:
            sys.modules["epy_docs"] = saved


def test_it_is_reachable_through_the_interpreter_studio_found(
    monkeypatch: pytest.MonkeyPatch, engine_hidden: None
) -> None:
    monkeypatch.setenv(_backends.ENV_DOCS_PYTHON, sys.executable)
    assert docs_bridge.epy_docs_available() is True


def test_it_is_not_reachable_when_there_is_nothing_to_reach(
    monkeypatch: pytest.MonkeyPatch, engine_hidden: None
) -> None:
    monkeypatch.delenv(_backends.ENV_DOCS_PYTHON, raising=False)
    assert docs_bridge.epy_docs_available() is False


def test_the_vocabularies_come_from_the_family(
    monkeypatch: pytest.MonkeyPatch, engine_hidden: None
) -> None:
    # Listed with no engine at all, because the dialog fills its combos
    # in its CONSTRUCTOR: a window that asked the engine could not be
    # built inside the bundle, where the engine cannot be imported.
    monkeypatch.delenv(_backends.ENV_DOCS_PYTHON, raising=False)
    assert docs_bridge.list_layouts() == list(APPEARANCES)
    assert docs_bridge.list_document_types() == list(DOCUMENT_TYPES)


class _Recorder:
    """Stands in for epy_export.render and keeps what it was asked."""

    def __init__(self) -> None:
        self.engine_id = ""
        self.formats: list[str] = []
        self.options: RenderOptions | None = None

    def __call__(
        self,
        source: Path,
        output_dir: Path,
        *,
        engine_id: str,
        formats: list[str],
        options: RenderOptions | None = None,
    ) -> list[Path]:
        self.engine_id = engine_id
        self.formats = list(formats)
        self.options = options
        return [output_dir / f"{source.stem}.{name}" for name in formats]


def _rendered(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, **kwargs: object
) -> _Recorder:
    recorder = _Recorder()
    monkeypatch.setattr(docs_bridge, "render", recorder)
    monkeypatch.setattr(docs_bridge, "available", lambda engine_id: True)
    source = tmp_path / "charla.md"
    source.write_text("# Titulo\n", encoding="utf-8")
    docs_bridge.render_document(
        source_path=source,
        layout="technical",
        document_type="notebook",
        output_dir=tmp_path / "out",
        **kwargs,  # type: ignore[arg-type]
    )
    return recorder


def test_a_deck_is_read_as_markdown_not_as_quarto(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # A deck is Markdown with slide syntax, not a Quarto document with
    # executable cells. Declared rather than guessed from the suffix,
    # because the two entry points are different methods on the writer
    # and guessing gives one of them the wrong reader.
    options = _rendered(monkeypatch, tmp_path, pdf=True, html=False).options
    assert options is not None
    assert options.source_kind == "markdown"


def test_the_choices_travel(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    recorder = _rendered(monkeypatch, tmp_path, pdf=False, html=True)
    assert recorder.engine_id == "docs"
    assert recorder.formats == ["html"]
    assert recorder.options is not None
    assert recorder.options.appearance == "technical"
    assert recorder.options.document_type == "notebook"


def test_an_absent_engine_says_it_is_an_add_on(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, engine_hidden: None
) -> None:
    # This engine is not something you install, it is something you buy,
    # and "install it, or choose another engine" is useless to a reader.
    monkeypatch.delenv(_backends.ENV_DOCS_PYTHON, raising=False)
    source = tmp_path / "charla.md"
    source.write_text("# T\n", encoding="utf-8")
    with pytest.raises(docs_bridge.BridgeUnavailableError) as raised:
        docs_bridge.render_document(
            source_path=source,
            layout="corporate",
            document_type="report",
            output_dir=tmp_path / "out",
            pdf=True,
            html=False,
        )
    message = str(raised.value)
    assert "commercial add-on" in message
    assert "anmingenieria.com" in message


def test_one_condition_carries_one_name() -> None:
    from epy_export import EngineUnavailableError

    assert docs_bridge.BridgeUnavailableError is EngineUnavailableError


def test_the_bridge_never_names_the_engine_itself() -> None:
    # Its charter: the only module that may reference epy_docs. It keeps
    # that promise by not referencing it at all -- the engine is named
    # once, in the shared catalogue.
    import inspect

    source = inspect.getsource(docs_bridge)
    assert "import epy_docs" not in source
    assert "DocumentWriter" not in source
