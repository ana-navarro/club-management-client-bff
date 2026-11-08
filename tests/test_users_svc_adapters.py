import json
from collections.abc import Callable

import httpx
import pytest

from src.domain.ports.auth_ports import UpstreamError
from src.infra.adapters.users_svc_adapters import (
    ClientProvider,
    ForgotPasswordAdapter,
    GetCurrentUserAdapter,
    LoginAdapter,
    RefreshTokenAdapter,
    ResetPasswordAdapter,
    UpdatePreferencesAdapter,
)


def provider_for(handler: Callable[[httpx.Request], httpx.Response]) -> ClientProvider:
    client = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(handler))
    return lambda: client


def test_login_forwards_the_client_address_and_browser() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"token": "jwt"})

    body = {"email": "a@b.c", "ip": "1.2.3.4", "userAgent": "Firefox"}
    result = LoginAdapter(provider_for(handler))(body)

    assert result == {"token": "jwt"}
    assert seen[0].url.path == "/auth/login"
    assert json.loads(seen[0].content) == body


def test_refresh_sends_the_token() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/auth/refresh"
        assert request.headers["authorization"] == "Bearer jwt"
        return httpx.Response(200, json={"token": "new"})

    assert RefreshTokenAdapter(provider_for(handler))("Bearer jwt") == {"token": "new"}


def test_forgot_and_reset_password_send_the_body() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(204)

    ForgotPasswordAdapter(provider_for(handler))({"email": "a@b.c"})
    ResetPasswordAdapter(provider_for(handler))({"token": "t", "password": "p"})

    assert paths == ["/auth/forgot-password", "/auth/reset-password"]


def test_get_and_update_user() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"method": request.method, "path": request.url.path})

    provider = provider_for(handler)
    assert GetCurrentUserAdapter(provider)("Bearer jwt") == {"method": "GET", "path": "/users/me"}
    assert UpdatePreferencesAdapter(provider)("Bearer jwt", {"theme": "dark"}) == {
        "method": "PATCH",
        "path": "/users/me/preferences",
    }


def test_keeps_the_status_and_code_from_the_service() -> None:
    provider = provider_for(lambda _: httpx.Response(401, json={"error": "invalid_credentials"}))

    with pytest.raises(UpstreamError) as error:
        LoginAdapter(provider)({})

    assert (error.value.status_code, error.value.code) == (401, "invalid_credentials")


@pytest.mark.parametrize(
    "response",
    [httpx.Response(500, text="not json"), httpx.Response(500, json=["list"])],
)
def test_handles_unexpected_error_bodies(response: httpx.Response) -> None:
    with pytest.raises(UpstreamError) as error:
        LoginAdapter(provider_for(lambda _: response))({})

    assert error.value.code == "internal_error"


def test_reports_an_unavailable_service() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("refused", request=request)

    with pytest.raises(UpstreamError) as error:
        LoginAdapter(provider_for(handler))({})

    assert (error.value.status_code, error.value.code) == (503, "service_unavailable")


def test_every_call_says_it_comes_from_the_client_system() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={})

    provider = provider_for(handler)
    LoginAdapter(provider)({"email": "a@b.c"})
    RefreshTokenAdapter(provider)("Bearer jwt")
    GetCurrentUserAdapter(provider)("Bearer jwt")
    UpdatePreferencesAdapter(provider)("Bearer jwt", {"theme": "dark"})

    assert [request.headers["x-app-type"] for request in seen] == ["CLIENT"] * 4
