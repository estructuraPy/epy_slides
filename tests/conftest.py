r"""Shared pytest fixtures for the epy_slides test-suite.

A single ``QApplication`` is created for the whole session so the widget
and dialog tests can build real Qt objects headlessly. The Qt platform is
forced to ``offscreen`` before the application is constructed, so no display
server is required on CI.

``epy_slides`` is imported here — before any test module — so its
``_pin_system_icu()`` bootstrap runs ahead of every ``PySide6`` import
(conda's ``Library\bin`` ICU shadows the Windows system ICU Qt links
against; see epy_reports for the same guard).

The session teardown flushes every pending ``deleteLater()`` and destroys
leftover widgets and the ``QApplication`` while the interpreter is still
healthy: test fixtures queue deletions that no event loop ever processes,
and the zombie WebEngine views otherwise crash Qt's native teardown at
process exit (0xC0000005 after all tests passed).
"""

from __future__ import annotations

import os
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import epy_slides  # noqa: E402, F401  — must precede any PySide6 import (ICU pin)


@pytest.fixture(scope="session")
def qapp():
    """Provide one session-scoped offscreen ``QApplication``."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app


@pytest.fixture(autouse=True)
def _isolated_settings(monkeypatch, tmp_path):
    """Route ``QSettings(org, app)`` to one INI file per scope, per test.

    The two-argument constructor ignores ``setDefaultFormat`` (Qt
    documents it) and goes to the registry, so the ``setPath(IniFormat)``
    fixtures the window tests carried were no-ops that LOOKED like
    isolation: every run read the developer's real theme and language
    and wrote them back. Replacing the constructor the window resolves
    is real isolation, and one file per (organisation, application)
    pair keeps the scopes as distinct as the registry keeps them.
    """
    from PySide6.QtCore import QSettings

    from epy_slides import app as app_module

    def scratch(organisation: str, name: str = "") -> QSettings:
        return QSettings(
            str(tmp_path / f"{organisation}__{name}.ini"),
            QSettings.Format.IniFormat,
        )

    monkeypatch.setattr(app_module, "QSettings", scratch)


@pytest.fixture(scope="session", autouse=True)
def _qt_session_teardown():
    """Destroy queued/leftover Qt objects before interpreter shutdown."""
    yield
    if "PySide6.QtWidgets" not in sys.modules:
        return
    from PySide6.QtCore import QEvent
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        return
    # Run the deletions the fixtures queued with deleteLater().
    app.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    app.processEvents()
    import shiboken6  # noqa: PLC0415

    # Widgets first, app last; delete the C++ objects directly (close()
    # would run app close-handlers against torn-down test state).
    for widget in QApplication.topLevelWidgets():
        if shiboken6.isValid(widget):
            shiboken6.delete(widget)
    app.processEvents()
    app.processEvents()
    shiboken6.delete(app)
