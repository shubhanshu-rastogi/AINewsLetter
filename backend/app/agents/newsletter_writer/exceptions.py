"""Exceptions for the newsletter writer agent."""

from __future__ import annotations


class WriterError(Exception):
    """Base class for newsletter generation failures."""


class NoContentError(WriterError):
    """Raised when there are no verified articles to write from."""


class UnknownSectionError(WriterError):
    """Raised when a regeneration target section is not recognized."""
