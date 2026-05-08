"""Sanity check that the empty Marduk package imports."""

import marduk


def test_package_imports():
    assert marduk.__version__ == "0.0.1"


def test_public_api_is_empty():
    assert marduk.__all__ == []
