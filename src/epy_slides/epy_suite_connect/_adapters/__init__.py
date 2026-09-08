"""Optional bridges from epy_slides to sibling epy_* suite packages.

Modules here are the only ones in epy_slides that may reference another
``epy_*`` package by name. Every such reference is a real Python import,
but the optional engines are reached through ``epy_export``, which
answers whether they can be reached at all before anything is loaded --
so importing ``epy_slides`` never requires an optional package to be
installed.
"""

from __future__ import annotations

__all__: list[str] = []
