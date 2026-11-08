import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

from src.config.create_app_config import create_app
from src.domain.ports.auth_ports import CallbackResult, JsonObject, UpstreamError
from src.domain.usecases.social_login_usecases import SocialLoginUsecases
from src.infra.adapters.users_svc_adapters import (
    SocialCallbackAdapter,
    SocialLinkConfirmAdapter,
    SocialLinkDeclineAdapter,
    SocialLinkPreviewAdapter,
    SocialSessionAdapter,
)

USER = {
    "id": "u1",
    "name": "Ana",
    "email": "a@b.c",
    "type": "CLIENT",
    "clubs": [],
    "preferences": {"theme": None, "language": None},
}
SESSION = {"token": "jwt", "expiresAt": "2026-01-01T12:00:00Z", "renewAt": "2026-01-01T11:30:00Z"}

Handler = Callable[[httpx.Request], httpx.Response]


def routes_handler(
    routes: dict[str, httpx.Response],
) -> tuple[Handler, list[httpx.Request]]:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return routes[f"{request.method} {request.url.path}"]

    return handler, seen


def client_for(
    routes: dict[str, httpx.Response], env: dict[str, str] | None = None
) -> tuple[TestClient, list[httpx.Request]]:
    handler, seen = routes_handler(routes)
    http = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(handler))
    app = create_app(lambda: http, env or {"CLIENT_APP_URL": "http://localhost:8080"})
    return TestClient(app, raise_server_exceptions=False, follow_redirects=False), seen


def body_of(request: httpx.Request) -> Any:
    return json.loads(request.content)


class TestStart:
    def test_sets_the_binding_cookie_and_redirects_to_the_provider(self) -> None:
        client, seen = client_for(
            {
                "POST /auth/social/google/authorization": httpx.Response(
                    200, json={"url": "https://accounts.test/auth?x=1"}
                )
            }
        )
        response = client.get("/auth/google/start?language=en")

        assert response.status_code == 302
        assert response.headers["location"] == "https://accounts.test/auth?x=1"
        cookie = response.headers["set-cookie"]
        assert "oauth_binding=" in cookie
        assert "HttpOnly" in cookie
        assert "Max-Age=600" in cookie
        assert "Path=/api/auth/" in cookie
        assert "SameSite=lax" in cookie
        assert "Secure" not in cookie
        sent = body_of(seen[0])
        assert sent["language"] == "en"
        assert len(sent["binding"]) >= 32
        assert seen[0].headers["x-app-type"] == "CLIENT"

    def test_marks_the_cookie_secure_on_https(self) -> None:
        client, _ = client_for(
            {"POST /auth/social/facebook/authorization": httpx.Response(200, json={"url": "u"})},
            {"CLIENT_APP_URL": "https://club.test"},
        )
        assert "Secure" in client.get("/auth/facebook/start").headers["set-cookie"]

    def test_ignores_an_unknown_language(self) -> None:
        client, seen = client_for(
            {"POST /auth/social/google/authorization": httpx.Response(200, json={"url": "u"})}
        )
        client.get("/auth/google/start?language=fr")
        assert "language" not in body_of(seen[0])

    def test_sends_the_login_page_an_error_when_the_provider_is_not_configured(self) -> None:
        client, _ = client_for(
            {
                "POST /auth/social/google/authorization": httpx.Response(
                    503, json={"error": "provider_unavailable"}
                )
            }
        )
        response = client.get("/auth/google/start")
        assert response.headers["location"] == "/login?social_error=provider_unavailable"

    def test_answers_404_for_an_unknown_provider(self) -> None:
        client, seen = client_for({})
        assert client.get("/auth/instagram/start").status_code == 404
        assert seen == []


class TestCallback:
    def callback(
        self, answer: httpx.Response, query: str = "code=c&state=s", cookie: str | None = "b1"
    ) -> tuple[httpx.Response, list[httpx.Request]]:
        client, seen = client_for({"POST /auth/social/google/callback": answer})
        if cookie:
            client.cookies.set("oauth_binding", cookie, path="/auth/")
        response = client.get(
            f"/auth/google/callback?{query}",
            headers={"x-real-ip": "1.2.3.4", "user-agent": "Firefox"},
        )
        return response, seen

    def test_sends_the_code_in_the_fragment_and_deletes_the_cookie(self) -> None:
        response, seen = self.callback(httpx.Response(200, json={"code": "a/b"}))

        assert response.status_code == 302
        assert response.headers["location"] == "/auth/callback#code=a%2Fb"
        assert 'oauth_binding=""' in response.headers["set-cookie"]
        assert "Max-Age=0" in response.headers["set-cookie"]
        assert body_of(seen[0]) == {
            "binding": "b1",
            "state": "s",
            "code": "c",
            "ip": "1.2.3.4",
            "userAgent": "Firefox",
        }

    def test_asks_to_check_the_email_on_a_first_facebook_entry(self) -> None:
        response, _ = self.callback(httpx.Response(202, json={"pending": "email_confirmation"}))
        assert response.headers["location"] == "/login?social_notice=check_email"

    @pytest.mark.parametrize(
        ("code", "expected"),
        [
            ("cancelled", "cancelled"),
            ("email_required", "email_required"),
            ("invalid_credentials", "invalid_credentials"),
            ("provider_unavailable", "provider_unavailable"),
            ("invalid_state", "invalid_state"),
            ("something_else", "provider_unavailable"),
        ],
    )
    def test_sends_only_the_error_code_to_the_login(self, code: str, expected: str) -> None:
        response, _ = self.callback(httpx.Response(400, json={"error": code}))
        assert response.headers["location"] == f"/login?social_error={expected}"

    def test_forwards_a_provider_error(self) -> None:
        _, seen = self.callback(
            httpx.Response(400, json={"error": "cancelled"}), query="error=access_denied&state=s"
        )
        assert body_of(seen[0])["error"] == "access_denied"
        assert "code" not in body_of(seen[0])

    @pytest.mark.parametrize(("query", "cookie"), [("code=c&state=s", None), ("code=c", "b1")])
    def test_refuses_a_return_without_cookie_or_state(self, query: str, cookie: str | None) -> None:
        response, seen = self.callback(httpx.Response(200, json={"code": "x"}), query, cookie)
        assert response.headers["location"] == "/login?social_error=invalid_state"
        assert seen == []


class TestSession:
    def test_returns_the_session_and_saves_the_missing_preferences(self) -> None:
        updated = {**USER, "preferences": {"theme": "dark", "language": "en"}}
        client, seen = client_for(
            {
                "POST /auth/social/session": httpx.Response(
                    200, json={**SESSION, "user": {**USER, "passwordHash": "x"}}
                ),
                "PATCH /users/me/preferences": httpx.Response(200, json=updated),
            }
        )
        response = client.post(
            "/auth/social/session", json={"code": "c", "language": "en", "theme": "dark"}
        )

        assert response.status_code == 200
        assert response.json() == {**SESSION, "user": updated}
        assert body_of(seen[0]) == {"code": "c"}
        assert seen[1].headers["authorization"] == "Bearer jwt"

    def test_repeats_an_invalid_code(self) -> None:
        client, _ = client_for(
            {
                "POST /auth/social/session": httpx.Response(
                    401, json={"error": "invalid_social_code"}
                )
            }
        )
        response = client.post("/auth/social/session", json={"code": "c"})
        assert response.status_code == 401
        assert response.json() == {"error": "invalid_social_code"}


class TestLink:
    def test_previews_only_the_contract_fields(self) -> None:
        preview = {"provider": "facebook", "profileName": "Ana FB", "email": "a@b.c"}
        client, _ = client_for(
            {
                "POST /auth/social/link/preview": httpx.Response(
                    200, json={**preview, "subject": "x"}
                )
            }
        )
        response = client.post("/auth/social/link/preview", json={"token": "t"})
        assert response.json() == preview

    def test_confirms_and_declines(self) -> None:
        client, seen = client_for(
            {
                "POST /auth/social/link/confirm": httpx.Response(204),
                "POST /auth/social/link/decline": httpx.Response(204),
            }
        )
        assert client.post("/auth/social/link/confirm", json={"token": "t"}).status_code == 204
        assert client.post("/auth/social/link/decline", json={"token": "t"}).status_code == 204
        assert [body_of(request) for request in seen] == [{"token": "t"}, {"token": "t"}]

    def test_repeats_an_invalid_link(self) -> None:
        client, _ = client_for(
            {
                "POST /auth/social/link/confirm": httpx.Response(
                    400, json={"error": "invalid_social_link"}
                )
            }
        )
        response = client.post("/auth/social/link/confirm", json={"token": "t"})
        assert response.json() == {"error": "invalid_social_link"}

    def test_refuses_an_empty_token(self) -> None:
        client, seen = client_for({})
        assert client.post("/auth/social/link/preview", json={"token": ""}).status_code == 400
        assert seen == []


def test_adapters_read_the_answers_of_the_users_service() -> None:
    handler, seen = routes_handler(
        {
            "POST /auth/social/google/callback": httpx.Response(200, json={"code": "x"}),
            "POST /auth/social/facebook/callback": httpx.Response(202, json={}),
            "POST /auth/social/session": httpx.Response(200, json=SESSION),
            "POST /auth/social/link/preview": httpx.Response(200, json={"email": "a@b.c"}),
            "POST /auth/social/link/confirm": httpx.Response(204),
            "POST /auth/social/link/decline": httpx.Response(204),
        }
    )
    http = httpx.Client(base_url="https://users-svc", transport=httpx.MockTransport(handler))

    def provider() -> httpx.Client:
        return http

    assert SocialCallbackAdapter(provider)("google", {}) == CallbackResult(code="x")
    assert SocialCallbackAdapter(provider)("facebook", {}) == CallbackResult(code=None)
    assert SocialSessionAdapter(provider)({"code": "c"}) == SESSION
    assert SocialLinkPreviewAdapter(provider)({"token": "t"}) == {"email": "a@b.c"}
    SocialLinkConfirmAdapter(provider)({"token": "t"})
    SocialLinkDeclineAdapter(provider)({"token": "t"})
    assert len(seen) == 6


def test_start_turns_a_malformed_answer_into_provider_unavailable() -> None:
    def authorize(provider: str, body: JsonObject) -> JsonObject:
        return {}

    unused: Any = None

    usecases = SocialLoginUsecases(
        authorize=authorize,
        complete=unused,
        exchange_code=unused,
        preview_link=unused,
        confirm_link=unused,
        decline_link=unused,
        update_preferences=unused,
    )
    result = usecases.start("google", None)
    assert result.location == "/login?social_error=provider_unavailable"

    def failing(provider: str, body: JsonObject) -> JsonObject:
        raise UpstreamError(503, "service_unavailable")

    failed = SocialLoginUsecases(
        authorize=failing,
        complete=unused,
        exchange_code=unused,
        preview_link=unused,
        confirm_link=unused,
        decline_link=unused,
        update_preferences=unused,
    )
    assert failed.start("google", "en").location == "/login?social_error=provider_unavailable"
