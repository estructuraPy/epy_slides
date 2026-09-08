"""This application's export dialog: the family's window, in its scope.

Everything the window does is the family's and tested there. What this
module owns is the three things that differ between the editors, and
each of them fails silently when it is wrong: a dialog in the wrong
registry scope quietly overwrites another editor's last-used values,
and a missing translator leaves a Spanish window with English labels.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from epy_slides._ui import docs_export_dialog as ded


@pytest.fixture
def scratch_settings(tmp_path, monkeypatch):
    """Send QSettings to an INI file so the real registry is untouched."""
    from PySide6 import QtCore

    real = QtCore.QSettings

    def scratch(organisation: str, name: str) -> object:
        return real(
            str(tmp_path / f"{organisation}__{name}.ini"),
            real.Format.IniFormat,
        )

    from epy_export._ui import docs_export_dialog as shared

    monkeypatch.setattr(shared, "QSettings", scratch)
    return scratch


def test_it_is_the_family_window(qapp) -> None:
    from epy_export._ui import docs_export_dialog as shared

    assert issubclass(ded.DocsExportDialog, shared.DocsExportDialog)


def test_it_remembers_in_this_application_scope(
    qapp, scratch_settings, tmp_path: Path
) -> None:
    # Two editors on one machine must not overwrite each other's
    # choices. The scope is the only thing that keeps them apart.
    from epy_export import ORGANIZATION

    source = tmp_path / "charla.md"
    source.write_text("# T\n", encoding="utf-8")
    dialog = ded.DocsExportDialog(source)
    dialog._combo_layout.setCurrentText("academic")
    dialog.persist_settings()
    stored = scratch_settings(ORGANIZATION, "epy_slides")
    assert stored.value("docs_layout") == "academic"
    assert not (
        tmp_path / f"{ORGANIZATION}__epy_reports.ini"
    ).exists()


def test_it_speaks_this_application_language(
    qapp, scratch_settings, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The window builds its labels from the translators it is given. A
    # dialog with no translator opens in English inside a Spanish
    # application, and nothing says so.
    from epy_slides._core import _i18n as i18n

    seen: list[str] = []
    monkeypatch.setattr(
        i18n, "translate_widget", lambda root: seen.append("translated")
    )
    source = tmp_path / "charla.md"
    source.write_text("# T\n", encoding="utf-8")
    ded.DocsExportDialog(source)
    assert seen == ["translated"]


def test_the_worker_reaches_this_application_bridge(
    qapp, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # Resolved at call time, so replacing the bridge function works.
    # Bound at import, this test would pass while the real render went
    # somewhere else.
    from epy_slides.epy_suite_connect._adapters import docs_bridge

    seen: dict[str, object] = {}
    monkeypatch.setattr(
        docs_bridge, "render_document", lambda **kw: seen.update(kw)
    )
    ded._RenderWorker(
        tmp_path / "charla.md", "corporate", "report", tmp_path / "out",
        True, False,
    ).run()
    assert seen["layout"] == "corporate"
    assert seen["output_dir"] == tmp_path / "out"
