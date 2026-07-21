"""Import-isolation gate (headless / no-GUI-toolkit contract).

``epy_slides``'s root package facade (``SlideDeck``) imports only ``pathlib``
at module level, so a bare ``import epy_slides`` (and building a ``SlideDeck``
instance) must stay usable with no Qt binding installed at all.

Unlike its sibling ``epy_reports`` (where only ``to_pdf`` needs Qt),
``epy_slides.to_html`` is NOT Qt-free: the reveal.js render path pulls in
``epy_slides._core.epyson`` (theme/color helpers such as ``is_dark()``), which
imports ``PySide6.QtGui.QColor`` at module level for color math. This test
locks in that real, current coupling as a documented contract rather than
asserting a Qt-free path that doesn't exist — if the render path is ever
decoupled from Qt (e.g. ``QColor`` math replaced with a pure-Python color
util), update ``test_slidedeck_to_html_requires_qt`` to expect success
instead. The hook runs in a fresh subprocess BEFORE anything imports
epy_slides, so a cached module can never mask a regression.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from pathlib import Path

_SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")


def _run_isolated(blocked_modules: tuple[str, ...], probe: str) -> subprocess.CompletedProcess:
    header = (
        "import builtins\n"
        "_real_import = builtins.__import__\n"
        f"_blocked = {blocked_modules!r}\n"
        "\n"
        "def _fake_import(name, *args, **kwargs):\n"
        "    if any(name == b or name.startswith(b + '.') for b in _blocked):\n"
        "        raise ImportError('blocked for isolation test: ' + name)\n"
        "    return _real_import(name, *args, **kwargs)\n"
        "\n"
        "builtins.__import__ = _fake_import\n"
        "\n"
    )
    script = header + textwrap.dedent(probe).strip() + "\n"
    env = dict(os.environ)
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = _SRC_DIR + (os.pathsep + existing if existing else "")
    return subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=120, env=env,
    )


class TestImportWithoutPySide6:
    def test_import_succeeds(self):
        result = _run_isolated(("PySide6", "PyQt6", "PyQt5", "PySide2"), "import epy_slides\nprint('OK')")
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout

    def test_slidedeck_class_still_available(self):
        probe = """
            import epy_slides
            assert hasattr(epy_slides, "SlideDeck")
            print('OK')
        """
        result = _run_isolated(("PySide6", "PyQt6", "PyQt5", "PySide2"), probe)
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout

    def test_slidedeck_instantiates_without_qt(self):
        # Building a SlideDeck (no render) never touches Qt.
        probe = """
            import epy_slides
            deck = epy_slides.SlideDeck("# Slide 1\\n\\nBody text.")
            assert deck.theme_id == "corporate"
            print('OK')
        """
        result = _run_isolated(("PySide6", "PyQt6", "PyQt5", "PySide2"), probe)
        assert result.returncode == 0, result.stderr
        assert "OK" in result.stdout

    def test_slidedeck_to_html_requires_qt(self, tmp_path):
        # Documented current coupling (not a Qt-free path, unlike epy_reports):
        # to_html() -> renderer -> template -> epyson.is_dark() imports
        # PySide6.QtGui.QColor at module level. This locks in the real
        # behavior so a future decoupling is a deliberate test update, not a
        # silent surprise.
        out_path = (tmp_path / "isolated_deck.html").as_posix()
        probe = f"""
            import epy_slides
            deck = epy_slides.SlideDeck("# Slide 1\\n\\nBody text.")
            out_path = {out_path!r}
            deck.to_html(out_path)
            print('OK')
        """
        result = _run_isolated(("PySide6", "PyQt6", "PyQt5", "PySide2"), probe)
        assert result.returncode != 0
        assert "PySide6" in result.stderr
