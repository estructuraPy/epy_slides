"""Tests for the ``python -m epy_slides`` module entry point."""

from __future__ import annotations

import runpy

import pytest

import epy_slides.app as app_module


def test_module_entry_calls_main_and_exits(monkeypatch):
    """Running the package as ``__main__`` calls ``app.main`` and exits."""
    calls: list[object] = []

    def fake_main(argv=None):
        calls.append(argv)
        return 0

    monkeypatch.setattr(app_module, "main", fake_main)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("epy_slides", run_name="__main__")
    assert excinfo.value.code == 0
    assert calls == [None]


def test_module_entry_propagates_nonzero(monkeypatch):
    monkeypatch.setattr(app_module, "main", lambda argv=None: 3)
    with pytest.raises(SystemExit) as excinfo:
        runpy.run_module("epy_slides", run_name="__main__")
    assert excinfo.value.code == 3
