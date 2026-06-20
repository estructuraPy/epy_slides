"""Tests for the Windows file-association helpers.

The path/command builders are pure and run anywhere. The ``register`` /
``unregister`` round-trip writes only under ``HKEY_CURRENT_USER`` (no admin,
no machine-wide keys) and always cleans up after itself, so it is safe to
run on a developer machine or Windows CI. On non-Windows the public API
raises ``RuntimeError`` by contract, which is asserted instead.
"""

from __future__ import annotations

import sys

import pytest

from epy_slides import winreg_assoc
from epy_slides.winreg_assoc import (
    APP_KEY,
    APP_NAME,
    EXTENSIONS,
    PROGID,
    _icon_source,
    _is_frozen,
    _is_windows,
    _launcher_path,
    _open_command,
    open_default_apps_settings,
    register,
    unregister,
)

_WINDOWS = sys.platform == "win32"


# --------------------------------------------------------------- pure helpers


def test_constants():
    assert PROGID == "epy_slides.Document.1"
    assert APP_NAME == "epy_slides"
    assert APP_KEY == "Applications\\epy_slides.exe"
    assert ".md" in EXTENSIONS and ".markdown" in EXTENSIONS


def test_is_windows_matches_platform():
    assert _is_windows() == (sys.platform == "win32")


def test_is_frozen_false_under_pytest():
    # pytest is never a PyInstaller bundle.
    assert _is_frozen() is False


def test_launcher_path_returns_string():
    path = _launcher_path()
    assert isinstance(path, str)
    assert path  # non-empty


def test_open_command_quotes_and_appends_arg():
    cmd = _open_command()
    assert cmd.endswith('"%1"')
    assert cmd.count('"%1"') == 1


def test_open_command_when_launcher_quoted(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_launcher_path", lambda: '"C:\\app.exe"')
    assert _open_command() == '"C:\\app.exe" "%1"'


def test_open_command_when_launcher_unquoted(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_launcher_path", lambda: "epy_slides")
    assert _open_command() == '"epy_slides" "%1"'


def test_icon_source_format():
    icon = _icon_source()
    assert icon.endswith(",0")
    assert isinstance(icon, str)


def test_launcher_path_frozen(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", "C:\\frozen\\epy_slides.exe")
    assert _launcher_path() == "C:\\frozen\\epy_slides.exe"


def test_icon_source_frozen(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", "C:\\frozen\\epy_slides.exe")
    assert _icon_source() == '"C:\\frozen\\epy_slides.exe",0'


# --------------------------------------------------- open_default_apps_settings


def test_open_default_apps_settings_launches_uri(monkeypatch):
    if not _WINDOWS:
        assert open_default_apps_settings() is False
        return
    launched: list[str] = []
    import os

    monkeypatch.setattr(os, "startfile", lambda uri: launched.append(uri))
    assert open_default_apps_settings() is True
    assert launched[0].startswith("ms-settings:defaultapps")


def test_open_default_apps_settings_falls_back(monkeypatch):
    if not _WINDOWS:
        # The non-Windows contract (returns False) is asserted separately.
        return
    import os

    calls: list[str] = []

    def fake_startfile(uri):
        calls.append(uri)
        if len(calls) == 1:
            raise OSError("first URI not resolvable")

    monkeypatch.setattr(os, "startfile", fake_startfile)
    assert open_default_apps_settings() is True
    assert len(calls) == 2  # specific URI failed, fallback succeeded


# --------------------------------------------------- non-Windows API contract


def test_register_raises_off_windows(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_is_windows", lambda: False)
    with pytest.raises(RuntimeError):
        register()


def test_unregister_raises_off_windows(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_is_windows", lambda: False)
    with pytest.raises(RuntimeError):
        unregister()


def test_open_default_apps_settings_off_windows(monkeypatch):
    monkeypatch.setattr(winreg_assoc, "_is_windows", lambda: False)
    assert open_default_apps_settings() is False


# --------------------------------------------------- HKCU round-trip (Windows)


def test_register_unregister_round_trip():
    if not _WINDOWS:
        return  # round-trip is meaningless without a Windows registry
    import winreg

    try:
        changes = register(make_default=True)
        assert any("Registered application" in line for line in changes)

        # The ProgID key must exist after register().
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROGID}"
        ):
            pass
        # The capabilities tree must exist too.
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, f"Software\\{APP_NAME}\\Capabilities"
        ):
            pass
    finally:
        removed = unregister()
        assert isinstance(removed, list)

    # After unregister, the ProgID key must be gone.
    with pytest.raises(FileNotFoundError):
        winreg.OpenKey(
            winreg.HKEY_CURRENT_USER, f"Software\\Classes\\{PROGID}"
        )


def test_unregister_when_absent_returns_list():
    if not _WINDOWS:
        return
    # Calling unregister with nothing registered must not raise.
    result = unregister()
    assert isinstance(result, list)
