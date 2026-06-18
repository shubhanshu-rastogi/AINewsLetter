"""Exceptions for the review/feedback agents."""

from __future__ import annotations


class ReviewError(Exception):
    """Base class for review/feedback failures."""


class ReviewSessionNotFoundError(ReviewError):
    """Raised when a review session does not exist."""


class NewsletterNotFoundError(ReviewError):
    """Raised when a newsletter/draft does not exist."""


class InvalidReviewActionError(ReviewError):
    """Raised when an action is invalid for the current review state."""
