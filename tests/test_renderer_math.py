"""Reveal export: every equation reaches the page as TeX for MathJax."""

from __future__ import annotations

from epy_slides._core.renderer import render_revealjs

_DECK = """---
title: math probe
---

## Fracciones

$$
MC = \\frac{m_a}{m_s} \\times 100
$$

Inline: la fracción $\\frac{a}{b}$ y el producto $x^2$.
"""


def test_revealjs_keeps_tex_for_mathjax():
    html = render_revealjs(_DECK)
    # With --mathjax every formula stays TeX inside a math span; pandoc's
    # legacy HTML math (italic <em> runs) must not appear for equations.
    assert 'class="math display"' in html
    assert 'class="math inline"' in html


def test_revealjs_fraction_not_degraded():
    # Without --mathjax, pandoc 3.x legacy HTML math cannot represent \frac
    # and degrades it to raw TeX outside a math span ("Could not convert TeX
    # math" warning). With --mathjax the TeX survives verbatim for MathJax.
    html = render_revealjs(_DECK)
    assert "\\frac{m_a}{m_s}" in html
    assert "\\frac{a}{b}" in html
