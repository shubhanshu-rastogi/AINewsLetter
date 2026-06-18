"""Exceptions for the publishing agents.

``RetryablePublishError`` -> transient (timeout, rate limit, 5xx, network) -> retry.
``PermanentPublishError`` -> config/auth/missing-asset -> do NOT retry.
"""

from __future__ import annotations


class PublishError(Exception):
    """Base class for publishing failures."""


class RetryablePublishError(PublishError):
    """Transient failure - eligible for retry with backoff."""


class PermanentPublishError(PublishError):
    """Non-retryable failure (invalid config, auth, missing assets)."""


class PublicationNotApprovedError(PermanentPublishError):
    """Raised when attempting to publish a newsletter that is not approved."""


class ValidationFailedError(PermanentPublishError):
    """Raised when the publication package is incomplete."""
