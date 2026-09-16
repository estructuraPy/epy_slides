"""Tests for the ePy Suite interoperability bridge (``epy_suite_connect``).

This package is the only cross-suite interconnection point for
epy_slides; ``get_suite_info`` is the identity contract every other
``epy_*`` package's registry reads.
"""

from __future__ import annotations

import epy_slides
from epy_slides.epy_suite_connect import get_suite_info


def test_get_suite_info_reports_package_identity():
    info = get_suite_info()
    assert info["pkg"] == "epy_slides"
    assert info["version"] == epy_slides.__version__


def test_get_suite_info_carries_the_author_through():
    """This test recorded a defect and now records its fix.

    ``epy_slides`` declared ``__version__`` but never ``__author__``, so the
    contract fell to its own ``getattr(_pkg, "__author__", "")`` default and
    this library was an entry in the cross-suite registry with NO author --
    while epy_steel, epy_concrete, epy_masonry and epy_units all declare one.
    An unattributed entry sends a reader of a signed report to nobody.

    Read from the package rather than restated here: a literal would agree
    with itself forever and drift from the build silently.
    """
    info = get_suite_info()
    assert info["author"] == epy_slides.__author__
    assert info["author"].strip(), "an empty author is an unattributed entry"


def test_get_suite_info_returns_plain_dict_with_expected_keys():
    info = get_suite_info()
    assert isinstance(info, dict)
    assert set(info) == {"pkg", "version", "author"}
