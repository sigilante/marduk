"""Sanity check that the Marduk package imports and exposes its core surface."""

import marduk


def test_package_imports():
    assert marduk.__version__ == "0.0.1"


def test_public_api_includes_value_types_and_drivers():
    expected = {"Val", "Hol", "Nat", "Pin", "App", "Law",
                "evaluate", "force", "PlanError", "PlanLoop"}
    assert expected.issubset(set(marduk.__all__))
