"""Exceptions for the categorization agent."""

from __future__ import annotations


class CategorizationError(Exception):
    """Base class for categorization failures."""


class ClassificationError(CategorizationError):
    """Raised when an article cannot be classified."""
