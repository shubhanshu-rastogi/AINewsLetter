"""Exceptions for the relevance filter agent."""

from __future__ import annotations


class RelevanceError(Exception):
    """Base class for relevance filtering failures."""


class ScoringError(RelevanceError):
    """Raised when an article cannot be scored."""


class SelectionError(RelevanceError):
    """Raised when article selection fails."""
