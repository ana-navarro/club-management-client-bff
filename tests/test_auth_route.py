from typing import Any

import httpx
from fastapi.testclient import TestClient

from src.config.create_app_config import create_app

USER = {
    "id": "u1",
    "name": "Ana",
    "email": "a@b.c",
    "type": "CLIENT",
    "clubs": [{"id": "c1", "name": "Club"}],
    "preferences": {"theme": None, "language": None},
}
SESSION = {"token": "jwt", "expiresAt": "2026-01-01T12:00:00Z", "renewAt": "2026-01-01T11:30:00Z"}
LEAK = {"passwordHash": "secret", "tokenVersion": 3, "knownNetworks": ["x"]}


def client_for(routes: dict[str, httpx.Response]) -> tuple[TestClient, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes[f"{request.method} {request.url.path}"]

    http = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(handler))
    return TestClient(create_app(lambda: http), raise_server_exceptions=False), seen


def test_login_returns_only_the_contract_fields() -> None:
    body: dict[str, Any] = {
        **SESSION,
        "extra": "drop",
        "user": {**USER, **LEAK, "clubs": [{"id": "c1", "name": "Club", "secret": 1}]},
    }
    client, seen = client_for({"POST /auth/login": httpx.Response(200, json=body)})

    response = client.post(
        "/auth/login",
        json={"email": "a@b.c", "password": "p"},
        headers={"x-real-ip": "1.2.3.4", "user-agent": "Firefox"},
    )

    assert response.status_code == 200
    assert response.json() == {**SESSION, "user": USER}
    assert b'"ip":"1.2.3.4"' in seen[0].content
    assert b'"userAgent":"Firefox"' in seen[0].content
    assert b'"userType":"CLIENT"' in seen[0].content


def test_login_saves_session_preferences() -> None:
    updated = {**USER, "preferences": {"theme": "dark", "language": None}}
    client, seen = client_for(
        {
            "POST /auth/login": httpx.Response(200, json={**SESSION, "user": USER}),
            "PATCH /users/me/preferences": httpx.Response(200, json=updated),
        }
    )

    response = client.post(
        "/auth/login",
        json={"email": "a@b.c", "password": "p", "preferences": {"theme": "dark"}},
    )

    assert response.json()["user"]["preferences"]["theme"] == "dark"
    assert seen[1].headers["authorization"] == "Bearer jwt"


def test_login_keeps_the_error_from_the_service() -> None:
    client, _ = client_for(
        {"POST /auth/login": httpx.Response(401, json={"error": "invalid_credentials"})}
    )

    response = client.post("/auth/login", json={"email": "a@b.c", "password": "p"})

    assert response.status_code == 401
    assert response.json() == {"error": "invalid_credentials"}


def test_rejects_invalid_bodies_with_a_simple_error() -> None:
    client, seen = client_for({})

    response = client.post("/auth/login", json={"email": "a@b.c", "password": "secret", "x": 1})

    assert response.status_code == 400
    assert response.json() == {"error": "invalid_request"}
    assert "secret" not in response.text
    assert seen == []


def test_refresh() -> None:
    client, seen = client_for({"POST /auth/refresh": httpx.Response(200, json=SESSION)})

    response = client.post("/auth/refresh", headers={"authorization": "Bearer jwt"})

    assert response.json() == SESSION
    assert seen[0].headers["authorization"] == "Bearer jwt"


def test_protected_routes_need_a_token() -> None:
    client, seen = client_for({})

    assert client.post("/auth/refresh").status_code == 401
    assert client.get("/users/me").status_code == 401
    assert client.patch("/users/me/preferences", json={"theme": "dark"}).status_code == 401
    assert seen == []


def test_forgot_password_has_no_body() -> None:
    client, seen = client_for({"POST /auth/forgot-password": httpx.Response(202)})

    response = client.post("/auth/forgot-password", json={"email": "a@b.c", "language": "en"})

    assert response.status_code == 202
    assert response.content == b""
    assert b'"language":"en"' in seen[0].content


def test_reset_password_and_its_error_reason() -> None:
    client, _ = client_for({"POST /auth/reset-password": httpx.Response(204)})
    response = client.post("/auth/reset-password", json={"token": "t", "password": "p"})
    assert response.status_code == 204

    client, _ = client_for(
        {"POST /auth/reset-password": httpx.Response(400, json={"error": "weak_password"})}
    )
    response = client.post("/auth/reset-password", json={"token": "t", "password": "p"})
    assert (response.status_code, response.json()) == (400, {"error": "weak_password"})


def test_get_me_returns_only_the_contract_fields() -> None:
    client, _ = client_for({"GET /users/me": httpx.Response(200, json={**USER, **LEAK})})

    response = client.get("/users/me", headers={"authorization": "Bearer jwt"})

    assert response.json() == USER


def test_update_preferences() -> None:
    client, seen = client_for({"PATCH /users/me/preferences": httpx.Response(200, json=USER)})

    response = client.patch(
        "/users/me/preferences", json={"theme": "dark"}, headers={"authorization": "Bearer jwt"}
    )

    assert response.status_code == 200
    assert seen[0].content == b'{"theme":"dark"}'


def test_unavailable_service() -> None:
    def fail(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down", request=request)

    http = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(fail))
    client = TestClient(create_app(lambda: http))

    response = client.post("/auth/login", json={"email": "a@b.c", "password": "p"})

    assert (response.status_code, response.json()) == (503, {"error": "service_unavailable"})
