"""Attach the user-provided NodeSeek cookie without persisting or logging it."""

from .models import AccountConfig


def authentication_headers(account: AccountConfig) -> dict[str, str]:
    if account.auth_type != "cookie":
        raise ValueError("NodeSeek supports only cookie configuration in this project")
    cookie_header = account.secret
    return {"Cookie": cookie_header}
