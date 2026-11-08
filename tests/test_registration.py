import json
from collections.abc import Callable

import httpx
from fastapi.testclient import TestClient

from src.config.create_app_config import create_app
from src.domain.ports.auth_ports import ClientInfo, JsonObject
from src.domain.usecases.auth_usecases import RegistrationUsecases
from src.infra.adapters.users_svc_adapters import (
    RegisterAdapter,
    ResendVerificationAdapter,
    VerifyEmailAdapter,
)

SIGN_UP = {
    "name": "  Ana  ",
    "email": "ana@example.com",
    "password": "long-enough",
    "language": "en",
}


def client_for(
    handler: Callable[[httpx.Request], httpx.Response],
) -> TestClient:
    http = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(handler))
    return TestClient(create_app(lambda: http), raise_server_exceptions=False)


def recording(status: int, body: JsonObject | None = None) -> tuple[
    Callable[[httpx.Request], httpx.Response], list[httpx.Request]
]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(status, json=body) if body is not None else httpx.Response(status)

    return handler, seen


def test_adapters_call_the_users_service_as_the_client_system() -> None:
    handler, seen = recording(202)
    provider = lambda: httpx.Client(  # noqa: E731
        base_url="https://users-svc", transport=httpx.MockTransport(handler)
    )
    RegisterAdapter(provider)({"email": "a@b.c"})
    VerifyEmailAdapter(provider)({"token": "t"})
    ResendVerificationAdapter(provider)({"email": "a@b.c"})

    assert [request.url.path for request in seen] == [
        "/auth/register",
        "/auth/verify-email",
        "/auth/resend-verification",
    ]
    assert all(request.headers["x-app-type"] == "CLIENT" for request in seen)


def test_register_usecase_adds_the_gateway_address() -> None:
    bodies: list[JsonObject] = []

    def record(body: JsonObject) -> None:
        bodies.append(body)

    usecases = RegistrationUsecases(
        register_client=record, verify_email_link=record, resend_verification_link=record
    )
    usecases.register({"email": "a@b.c"}, ClientInfo(ip="1.2.3.4", user_agent=None))
    usecases.register({"email": "a@b.c"}, ClientInfo(ip=None, user_agent=None))
    usecases.verify_email({"token": "t"})
    usecases.resend_verification({"email": "a@b.c"})

    assert bodies == [
        {"email": "a@b.c", "ip": "1.2.3.4"},
        {"email": "a@b.c"},
        {"token": "t"},
        {"email": "a@b.c"},
    ]


def test_register_answers_202_and_sends_the_trimmed_name_and_address() -> None:
    handler, seen = recording(202)
    response = client_for(handler).post(
        "/auth/register", json=SIGN_UP, headers={"x-real-ip": "1.2.3.4"}
    )

    assert response.status_code == 202
    assert response.content == b""
    assert json.loads(seen[0].content) == {
        "name": "Ana",
        "email": "ana@example.com",
        "password": "long-enough",
        "language": "en",
        "ip": "1.2.3.4",
    }


def test_register_refuses_an_account_type_without_calling_the_service() -> None:
    handler, seen = recording(202)
    response = client_for(handler).post("/auth/register", json={**SIGN_UP, "type": "ADMIN"})

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}
    assert "long-enough" not in response.text
    assert seen == []


def test_register_repeats_the_errors_of_the_service() -> None:
    handler, _ = recording(429, {"error": "too_many_requests"})
    response = client_for(handler).post("/auth/register", json=SIGN_UP)

    assert response.status_code == 429
    assert response.json() == {"error": "too_many_requests"}


def test_verify_email_answers_204_or_the_invalid_link() -> None:
    ok, _ = recording(204)
    assert client_for(ok).post("/auth/verify-email", json={"token": "t"}).status_code == 204

    invalid, _ = recording(400, {"error": "invalid_verification_link"})
    response = client_for(invalid).post("/auth/verify-email", json={"token": "t"})
    assert response.status_code == 400
    assert response.json() == {"error": "invalid_verification_link"}


def test_resend_answers_202() -> None:
    handler, seen = recording(202)
    response = client_for(handler).post(
        "/auth/resend-verification", json={"email": "ana@example.com", "language": "pt-BR"}
    )

    assert response.status_code == 202
    assert json.loads(seen[0].content) == {"email": "ana@example.com", "language": "pt-BR"}
