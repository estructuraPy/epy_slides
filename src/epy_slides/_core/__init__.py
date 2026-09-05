"""Processing / render / export / authoring logic for epy_slides.

Holds the non-Qt implementation modules — rendering (``renderer.py``,
``_revealjs_theme.py``, ``template.py``), export (``_export_pdf.py``,
``_media_export.py``), authoring data (``slide_md.py``,
``snippets.py``, ``bib.py``, ``epyson.py``, ``latex_catalog.py``,
``templates.py``), i18n (``_i18n.py``) and the Windows file-association
helper (``winreg_assoc.py``) — plus ``_packaging``, dev-only build/release
tooling (icon generation, Windows/Linux installer assemblers,
screenshot/reference-deck regeneration scripts).

Only ``_packaging`` is excluded from the built wheel; see
``[tool.hatch.build.targets.wheel]`` in ``pyproject.toml``.
"""
