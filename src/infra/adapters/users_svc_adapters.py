from collections.abc import Callable
from typing import Any

import httpx

from src.domain.ports.auth_ports import CallbackResult, JsonObject, UpstreamError

ClientProvider = Callable[[], httpx.Client]

# Tells the users service which system is calling, so a client token is refused here.
APP_TYPE = "CLIENT"


def _send(
    provider: ClientProvider,
    method: str,
    path: str,
    json: JsonObject | None = None,
    authorization: str | None = None,
) -> httpx.Response:
    headers = {"X-App-Type": APP_TYPE}
    if authorization:
        headers["Authorization"] = authorization
    try:
        response = provider().request(method, path, json=json, headers=headers)
    except httpx.HTTPError as error:
        raise UpstreamError(503, "service_unavailable") from error
    if response.is_error:
        raise UpstreamError(response.status_code, _read_code(response))
    return response


def _read_code(response: httpx.Response) -> str:
    try:
        body: Any = response.json()
    except ValueError:
        return "internal_error"
    return str(body.get("error", "internal_error")) if isinstance(body, dict) else "internal_error"


class LoginAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> JsonObject:
        result: JsonObject = _send(self._provider, "POST", "/auth/login", json=body).json()
        return result


class RefreshTokenAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, authorization: str) -> JsonObject:
        response = _send(self._provider, "POST", "/auth/refresh", authorization=authorization)
        result: JsonObject = response.json()
        return result


class ForgotPasswordAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/forgot-password", json=body)


class ResetPasswordAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/reset-password", json=body)


class GetCurrentUserAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, authorization: str) -> JsonObject:
        response = _send(self._provider, "GET", "/users/me", authorization=authorization)
        result: JsonObject = response.json()
        return result


class UpdatePreferencesAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, authorization: str, body: JsonObject) -> JsonObject:
        response = _send(
            self._provider, "PATCH", "/users/me/preferences", json=body, authorization=authorization
        )
        result: JsonObject = response.json()
        return result


class RegisterAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/register", json=body)


class VerifyEmailAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/verify-email", json=body)


class ResendVerificationAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/resend-verification", json=body)


class SocialAuthorizationAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, provider: str, body: JsonObject) -> JsonObject:
        path = f"/auth/social/{provider}/authorization"
        response = _send(self._provider, "POST", path, json=body)
        result: JsonObject = response.json()
        return result


class SocialCallbackAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, provider: str, body: JsonObject) -> CallbackResult:
        response = _send(self._provider, "POST", f"/auth/social/{provider}/callback", json=body)
        if response.status_code == 202:
            return CallbackResult(code=None)
        result: JsonObject = response.json()
        return CallbackResult(code=str(result["code"]))


class SocialSessionAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> JsonObject:
        result: JsonObject = _send(self._provider, "POST", "/auth/social/session", json=body).json()
        return result


class SocialLinkPreviewAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> JsonObject:
        response = _send(self._provider, "POST", "/auth/social/link/preview", json=body)
        result: JsonObject = response.json()
        return result


class SocialLinkConfirmAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/social/link/confirm", json=body)


class SocialLinkDeclineAdapter:
    def __init__(self, provider: ClientProvider) -> None:
        self._provider = provider

    def __call__(self, body: JsonObject) -> None:
        _send(self._provider, "POST", "/auth/social/link/decline", json=body)
