"""Core infrastructure for epy_slides.

Currently holds ``_packaging`` — dev-only build/release tooling (icon
generation, Windows/Linux installer assemblers, screenshot/reference-deck
regeneration scripts). Excluded from the built wheel; see
``[tool.hatch.build.targets.wheel]`` in ``pyproject.toml``.
"""
