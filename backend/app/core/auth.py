"""Authentication abstraction (placeholder).

Provides a swappable provider interface so JWT / OAuth / SSO can be added later
without changing call sites. The default provider is permissive (development);
the existing ``require_reviewer`` token check remains the interim gate.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(slots=True)
class Principal:
    subject: str
    roles: tuple[str, ...] = ()
    authenticated: bool = False


class AuthProvider(ABC):
    @abstractmethod
    async def authenticate(self, authorization: str | None) -> Principal: ...


class AllowAllAuthProvider(AuthProvider):
    """Development default - returns an anonymous principal."""

    async def authenticate(self, authorization: str | None) -> Principal:
        return Principal(subject="anonymous", roles=("viewer",), authenticated=False)


class JWTAuthProvider(AuthProvider):
    """Placeholder for JWT validation (not implemented)."""

    async def authenticate(self, authorization: str | None) -> Principal:  # pragma: no cover
        raise NotImplementedError("JWT authentication is not implemented yet.")


_provider: AuthProvider = AllowAllAuthProvider()


def set_auth_provider(provider: AuthProvider) -> None:
    global _provider
    _provider = provider


def get_auth_provider() -> AuthProvider:
    return _provider
