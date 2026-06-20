"""Capture the epy_slides user-manual screenshots.

Renders the real Fluent-styled UI (main window + the dialogs the manual
walks through) to PNGs under ``src/epy_slides/assets/screenshots/`` so the
bundled ``welcome.md`` / ``welcome_es.md`` manuals show the actual program.

Run it headlessly::

    QT_QPA_PLATFORM=offscreen python tools/capture_screenshots.py

It writes both the English files (``editor.png`` …) and the Spanish
variants (``editor_es.png`` …) by toggling the live UI language.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# The native Windows platform is used on purpose: the ``offscreen`` plugin
# ships an empty font database on Windows and renders every Qt-native glyph
# as .notdef tofu. ``WA_DontShowOnScreen`` (set in ``grab_widget``) keeps the
# windows off the desktop while still laying them out for ``grab()``.
os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")
os.environ.setdefault(
    "QTWEBENGINE_CHROMIUM_FLAGS", "--no-sandbox --disable-gpu"
)

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtCore import (  # noqa: E402
    QElapsedTimer,
    QEventLoop,
    Qt,
    QTimer,
)
from PySide6.QtWidgets import QApplication, QDialog  # noqa: E402

from epy_slides import _i18n as i18n  # noqa: E402
from epy_slides import themes  # noqa: E402
from epy_slides.app import SlideWindow  # noqa: E402
from epy_slides.equation_dialog import EquationDialog  # noqa: E402
from epy_slides.figure_dialog import FigureDialog  # noqa: E402
from epy_slides.presentation_properties_dialog import (  # noqa: E402
    PresentationPropertiesDialog,
)
from epy_slides.slide_dialogs import NewSlideDialog  # noqa: E402
from epy_slides.table_dialog import TableDialog  # noqa: E402
from epy_slides.theme_editor_dialog import ThemeEditorDialog  # noqa: E402
from epy_slides.theme_gallery_dialog import ThemeGalleryDialog  # noqa: E402

OUT = ROOT / "src" / "epy_slides" / "assets" / "screenshots"

# A compact deck that exercises a layout, a component and a callout so the
# editor screenshot shows representative Markdown next to its live preview.
DEMO_DECK = """\
---
title: Quarterly review
author: ANM Ingeniería
theme: corporate
aspect-ratio: "16:9"
slide-number: true
footer: ANM Ingeniería
---

## Project status
<!-- layout: big-stat -->

:::: {.stats}
::: {.stat}
**98%**

[on schedule]{.stat-label}
:::
::: {.stat}
**3**

[open risks]{.stat-label}
:::
::::

## Next steps
<!-- layout: title-content -->

- Finalise the structural review
- Issue the construction set
- Brief the field team

::: {.callout-note title="Reminder"}
Export to **PDF**, **HTML** or **PowerPoint** from the *Export* menu.
:::
"""


def pump(app: QApplication, ms: int) -> None:
    """Spin the event loop for ``ms`` so async painting/rendering settles."""
    timer = QElapsedTimer()
    timer.start()
    while timer.elapsed() < ms:
        app.processEvents(QEventLoop.ProcessEventsFlag.AllEvents, 50)


def grab_widget(app: QApplication, widget, path: Path, settle: int) -> None:
    """Lay a widget out offscreen, let it settle, then save a grab."""
    widget.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    widget.show()
    pump(app, settle)
    pix = widget.grab()
    path.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(path))
    size = path.stat().st_size if path.exists() else 0
    print(f"  {path.name:32s} {pix.width()}x{pix.height()}  {size:,} B")


def sample_meta() -> dict[str, str]:
    """Front-matter values that pre-fill the properties dialog nicely."""
    return {
        "title": "Quarterly review",
        "subtitle": "Structural engineering update",
        "author": "Ing. Angel Navarro-Mora M.Sc.",
        "date": "2026-06-18",
        "theme": "corporate",
        "aspect-ratio": "16:9",
        "transition": "slide",
        "slide-number": "true",
        "footer": "ANM Ingeniería",
        "copyright": "© 2026 ANM Ingeniería",
    }


def capture_dialogs(app: QApplication, win: SlideWindow, suffix: str) -> None:
    """Capture every manual dialog for the active language."""
    specs = [
        # (stem, factory, optional (width, height) to show the full content)
        ("dlg_new_slide", lambda: NewSlideDialog(win), (470, 600)),
        (
            "presentation_properties",
            lambda: PresentationPropertiesDialog(win, sample_meta()),
            None,
        ),
        ("dlg_figure", lambda: FigureDialog(win), None),
        ("dlg_table", lambda: TableDialog(win), None),
        ("dlg_equation", lambda: EquationDialog(win), None),
        (
            "dlg_theme",
            lambda: ThemeEditorDialog(win, base_theme_id="corporate"),
            None,
        ),
        (
            "dlg_theme_gallery",
            lambda: ThemeGalleryDialog(win, current_id="corporate"),
            (640, 460),
        ),
    ]
    for stem, factory, size in specs:
        dlg: QDialog = factory()
        dlg.setModal(False)
        if size is not None:
            dlg.resize(*size)
        grab_widget(app, dlg, OUT / f"{stem}{suffix}.png", settle=250)
        dlg.close()
        dlg.deleteLater()
        pump(app, 50)


def capture_language(app: QApplication, win: SlideWindow, suffix: str) -> None:
    """Capture the editor and dialogs for whichever language is active."""
    grab_widget(app, win, OUT / f"editor{suffix}.png", settle=1500)
    capture_dialogs(app, win, suffix)


def main() -> int:
    """Boot the app offscreen and capture every manual screenshot."""
    app = QApplication.instance() or QApplication(sys.argv)
    themes.apply_palette(app, themes.get("corporate"))
    app.setStyleSheet(themes.qss_for(themes.get("corporate")))

    win = SlideWindow()
    win.resize(1280, 800)
    win.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    tab = win._current_tab()
    if tab is not None:
        tab.set_initial_text(DEMO_DECK, path=None)
    win.show()
    # Let reveal.js + MathJax paint the live preview before the first grab.
    pump(app, 3500)

    print("English:")
    capture_language(app, win, "")

    print("Spanish:")
    i18n.set_language("es")
    pump(app, 300)
    capture_language(app, win, "_es")

    # Stale screenshots inherited from the epy_reports clone that no longer map
    # to any epy_slides feature; remove them so the package stays honest.
    stale = [
        "dlg_checklist", "dlg_footnote", "dlg_xref", "dlg_bib",
        "document_properties",
    ]
    for stem in stale:
        for variant in (f"{stem}.png", f"{stem}_es.png"):
            target = OUT / variant
            if target.exists():
                target.unlink()
                print(f"  removed stale {variant}")

    QTimer.singleShot(0, app.quit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
