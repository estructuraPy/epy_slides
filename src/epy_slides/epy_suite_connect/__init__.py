"""epy_slides.epy_suite_connect — ePy Suite interoperability bridge.

epy_slides is the Markdown slide-editor library (live reveal.js preview, PDF /
HTML / PPTX export). This package is the ONLY cross-suite interconnection
point for epy_slides.

App-GUI family (shared toolkit with epy_reports / epy_papers / epy_draft). It
currently exposes the suite identity contract (``get_suite_info``) and hosts
the suite registry manifest.

Import-clean: only the standard library. It must never import epy_analysis or
any sibling library.
"""

from __future__ import annotations

__all__ = ["get_suite_info"]


def get_suite_info() -> dict:
    """Return package metadata for the cross-suite registry."""
    import epy_slides as _pkg

    return {
        "pkg": "epy_slides",
        "version": getattr(_pkg, "__version__", "0.0.0"),
        "author": getattr(_pkg, "__author__", ""),
    }
