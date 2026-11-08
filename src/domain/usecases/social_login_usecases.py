import secrets
from dataclasses import dataclass
from urllib.parse import quote

from src.domain.ports.auth_ports import (
    ClientInfo,
    JsonObject,
    SocialAuthorizationPort,
    SocialCallbackPort,
    SocialLinkActionPort,
    SocialLinkPreviewPort,
    SocialSessionPort,
    UpdatePreferencesPort,
    UpstreamError,
)
from src.domain.usecases.auth_usecases import save_missing_preferences

PROVIDERS = ("google", "facebook")

# The only codes the login page shows. Anything else becomes provider_unavailable.
KNOWN_ERRORS = {"cancelled", "email_required", "invalid_credentials", "provider_unavailable"}
INVALID_STATE = "invalid_state"


def login_error(code: str) -> str:
    return f"/login?social_error={code}"


@dataclass(frozen=True)
class StartResult:
    binding: str
    location: str


@dataclass(frozen=True)
class SocialLoginUsecases:
    """Only redirects the browser and keeps the binding cookie. users-svc validates and decides."""

    authorize: SocialAuthorizationPort
    complete: SocialCallbackPort
    exchange_code: SocialSessionPort
    preview_link: SocialLinkPreviewPort
    confirm_link: SocialLinkActionPort
    decline_link: SocialLinkActionPort
    update_preferences: UpdatePreferencesPort

    def start(self, provider: str, language: str | None) -> StartResult:
        """A random binding ties the attempt to this browser (research R1, R2)."""
        binding = secrets.token_urlsafe(32)
        body: JsonObject = {"binding": binding}
        if language:
            body["language"] = language
        try:
            url = str(self.authorize(provider, body)["url"])
        except (UpstreamError, KeyError):
            return StartResult(binding=binding, location=login_error("provider_unavailable"))
        return StartResult(binding=binding, location=url)

    def callback(
        self,
        provider: str,
        query: dict[str, str],
        binding: str | None,
        client: ClientInfo,
    ) -> str:
        """Returns the frontend path. Errors go to the login page with only a code."""
        state = query.get("state")
        if not binding or not state:
            return login_error(INVALID_STATE)

        body: JsonObject = {"binding": binding, "state": state}
        for name in ("code", "error"):
            if query.get(name):
                body[name] = query[name]
        if client.ip:
            body["ip"] = client.ip
        if client.user_agent:
            body["userAgent"] = client.user_agent

        try:
            result = self.complete(provider, body)
        except UpstreamError as error:
            known = error.code in KNOWN_ERRORS or error.code == INVALID_STATE
            return login_error(error.code if known else "provider_unavailable")
        if result.code is None:
            return "/login?social_notice=check_email"
        # In the fragment, so it never reaches a server, a log or the Referer (research R2).
        return f"/auth/callback#code={quote(result.code, safe='')}"

    def session(self, code: str, preferences: JsonObject) -> JsonObject:
        session = self.exchange_code({"code": code})
        return save_missing_preferences(self.update_preferences, session, preferences)

    def preview(self, token: str) -> JsonObject:
        return self.preview_link({"token": token})

    def confirm(self, token: str) -> None:
        self.confirm_link({"token": token})

    def decline(self, token: str) -> None:
        self.decline_link({"token": token})
