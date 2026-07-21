"""Bearer authentication isolated per configured NovalPie account."""

from __future__ import annotations

from typing import Protocol, TYPE_CHECKING

from .models import AccountConfig

if TYPE_CHECKING:
    from .client import HttpResponse


class AuthProvider(Protocol):
    def headers(self) -> dict[str, str]: ...
    def observe(self, response: "HttpResponse") -> None: ...
    def refresh(self) -> bool: ...


class BearerAuthProvider:
    def __init__(self, account: AccountConfig):
        if account.auth_type != "bearer":
            raise ValueError("NovalPie requires bearer authentication")
        self.account = account

    def headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.account.secret}"}

    def observe(self, response: "HttpResponse") -> None:
        return None

    def refresh(self) -> bool:
        return False


def build_auth_provider(account: AccountConfig) -> BearerAuthProvider:
    return BearerAuthProvider(account)


def authentication_headers(account: AccountConfig) -> dict[str, str]:
    return build_auth_provider(account).headers()
