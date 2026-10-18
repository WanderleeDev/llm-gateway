import secrets

from fastapi import Request

from app.deps import SettingsDep
from app.errors import APIError


def _unauthorized() -> APIError:
    return APIError(401, "Incorrect API key provided.", "authentication_error", "invalid_api_key")


def require_api_key(request: Request, settings: SettingsDep) -> None:
    scheme, _, token = request.headers.get("authorization", "").partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token:
        raise _unauthorized()

    # compare_digest sobre bytes: con str lanzaría TypeError ante caracteres no ASCII
    presented = token.encode()
    if not any(secrets.compare_digest(presented, key.encode()) for key in settings.api_keys):
        raise _unauthorized()
