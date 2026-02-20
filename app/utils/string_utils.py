"""String utility functions."""

from __future__ import annotations


def snake_to_title_case(snake_str: str) -> str:
    """Convert snake_case to Title Case. E.g. 'autonomous_system_org' -> 'Autonomous System Org'."""
    return " ".join(word.capitalize() for word in snake_str.split("_"))
