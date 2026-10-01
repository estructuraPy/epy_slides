"""epy_slides — Markdown slide editor with reveal.js preview.

Single public API for the suite (mirrors ``epy_reports.Report`` /
``epy_paper.Paper`` / ``epy_project.ProjectManager``)::

    from epy_slides import SlideDeck

    deck = SlideDeck.from_file("talk.md", theme="corporate")
    deck.to_html("talk.html")     # standalone reveal.js slideshow
    deck.to_pptx("talk.pptx")     # PowerPoint
    deck.to_pdf("talk.pdf")       # one slide per page (needs PySide6)

The GUI application is ``epy_slides.app:main``; the facade below is the
importable, scriptable entry point and pulls in Qt only for ``to_pdf``.
"""

from __future__ import annotations

__version__ = "0.5.0"
#: Declared so the cross-suite registry can attribute this library. Without it
#: `epy_suite_connect.get_suite_info` fell to its own `getattr(..., "")`
#: default and epy_slides was an entry in the registry with no author, while
#: epy_steel, epy_concrete, epy_masonry and epy_units all declare one. Same
#: defect found and fixed in epy_signal on the same pass.
__author__ = "Ing. Angel Navarro-Mora M.Sc."

__all__ = ["SlideDeck", "__version__"]


# The ICU pin lived here, in epy_reports and in epy_papers, and this
# copy's docstring said outright that it mirrored the first. It is
# epy_export's now. The call stays explicit and stays HERE, ahead of
# anything that touches Qt: the ordering is the whole point.
from epy_export import pin_system_icu

pin_system_icu()



from epy_slides._core._deck import SlideDeck  # noqa: E402
