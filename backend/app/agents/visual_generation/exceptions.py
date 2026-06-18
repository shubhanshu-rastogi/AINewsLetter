"""Exceptions for the visual generation agent."""

from __future__ import annotations


class VisualGenerationError(Exception):
    """Base class for visual generation failures."""


class AssetStorageError(VisualGenerationError):
    """Raised when an asset cannot be stored."""


class ImageGenerationError(VisualGenerationError):
    """Raised when AI image generation fails."""


class VisualNotFoundError(VisualGenerationError):
    """Raised when a referenced visual does not exist."""
