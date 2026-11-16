"""Shared test utilities."""

from typing import TypeVar

T = TypeVar("T")


def present(value: T | None) -> T:
    """Fail the test when a database lookup unexpectedly returns ``None``."""
    assert value is not None
    return value
