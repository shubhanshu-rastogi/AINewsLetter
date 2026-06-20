"""Secret provider abstraction + log masking.

Secrets are read through a provider so the backend can be swapped (env vars now;
Vault / cloud secret managers later) without touching call sites. Secret values
are masked before they ever reach logs.
"""

from __future__ import annotations

import os
import re
from abc import ABC, abstractmethod

# Settings whose values must never appear in logs.
SECRET_SETTING_NAMES = (
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "NOTION_API_KEY",
    "BEEHIIV_API_KEY",
    "LINKEDIN_CLIENT_SECRET",
    "LINKEDIN_CLIENT_ID",
    "DATABASE_URL",
    "DATABASE_URL_OVERRIDE",
    "POSTGRES_PASSWORD",
    "SECRET_KEY",
    "REVIEW_AUTH_TOKEN",
    "REDIS_URL",
)

# Heuristics for masking secret-shaped values in free text.
_TOKEN_PATTERNS = [
    re.compile(r"(sk-[A-Za-z0-9]{8,})"),  # OpenAI-style keys
    re.compile(r"(Bearer\s+)[A-Za-z0-9._\-]{8,}", re.I),  # bearer tokens
    re.compile(r"(://[^:/@\s]+:)[^@/\s]+(@)"),  # creds in URLs
]


class SecretProvider(ABC):
    @abstractmethod
    def get(self, name: str, default: str | None = None) -> str | None: ...


class EnvSecretProvider(SecretProvider):
    """Reads secrets from environment variables (the default backend)."""

    def get(self, name: str, default: str | None = None) -> str | None:
        return os.environ.get(name, default)


_provider: SecretProvider = EnvSecretProvider()


def set_secret_provider(provider: SecretProvider) -> None:
    global _provider
    _provider = provider


def get_secret(name: str, default: str | None = None) -> str | None:
    return _provider.get(name, default)


def mask_secret(value: str | None, *, show: int = 4) -> str:
    """Mask a secret value, optionally revealing the last ``show`` chars."""
    if not value:
        return ""
    if len(value) <= show:
        return "*" * len(value)
    return "*" * (len(value) - show) + value[-show:]


def mask_text(text: str) -> str:
    """Mask secret-shaped substrings (URL creds, bearer tokens, API keys)."""
    masked = text
    for pattern in _TOKEN_PATTERNS:
        if pattern.groups == 2:
            masked = pattern.sub(lambda m: f"{m.group(1)}***{m.group(2)}", masked)
        else:
            masked = pattern.sub(lambda m: f"{m.group(1)[:6]}***", masked)
    return masked
