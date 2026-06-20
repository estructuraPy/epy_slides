"""Shared pytest fixtures for the epy_slides test-suite.

A single ``QApplication`` is created for the whole session so the widget
and dialog tests can build real Qt objects headlessly. The Qt platform is
forced to ``offscreen`` before the application is constructed, so no display
server is required on CI.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    """Provide one session-scoped offscreen ``QApplication``."""
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    return app
