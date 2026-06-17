"""Exceptions for the source collection agent."""

from __future__ import annotations


class CollectionError(Exception):
    """Base class for collection failures."""


class FetchError(CollectionError):
    """Raised when an HTTP fetch fails after retries."""


class FeedParseError(CollectionError):
    """Raised when a feed cannot be parsed."""


class RobotsDisallowedError(CollectionError):
    """Raised when robots.txt disallows fetching a URL."""


class UnsupportedCollectionMethodError(CollectionError):
    """Raised when no collector is available for a method."""
