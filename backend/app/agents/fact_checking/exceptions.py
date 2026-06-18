"""Exceptions for the fact-checking agent."""

from __future__ import annotations


class FactCheckError(Exception):
    """Base class for fact-checking failures."""


class SourceVerificationError(FactCheckError):
    """Raised when source verification fails."""


class ClaimExtractionError(FactCheckError):
    """Raised when claim extraction fails."""
