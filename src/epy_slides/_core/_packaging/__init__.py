"""Build and release tooling for epy_slides (dev-only, wheel-excluded).

Contents:
    make_icon.py            — generate ``assets_build/epy_slides.ico`` (+ .png)
                               from the source logo.
    capture_screenshots.py  — capture the bundled user-manual screenshots
                               under ``_config/_assets/screenshots/``.
    make_reference_pptx.py  — regenerate the per-theme PowerPoint reference
                               decks under ``_config/_assets/reference_pptx/``.
    assets_build/           — source images for the application icon.
    linux/build_deb.py      — pure-Python .deb package assembler.
    windows/epy_slides.iss  — Inno Setup script for the Windows installer.
    dist/                   — gitignored installer build output.

None of this ships in the wheel — see ``force-exclude`` in
``[tool.hatch.build.targets.wheel]`` (``pyproject.toml``). Scripts are run
directly from a source checkout (``python src/epy_slides/_core/_packaging/...``),
matching the CI invocations in ``.github/workflows/installers.yml``.
"""
