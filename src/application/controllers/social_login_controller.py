from fastapi import Request, Response, status
from fastapi.responses import RedirectResponse

from src.application.controllers.auth_controller import read_client
from src.application.dto.auth_dto import (
    LoginResponseDto,
    SocialLinkPreviewDto,
    SocialLinkRequestDto,
    SocialSessionRequestDto,
)
from src.domain.ports.auth_ports import UpstreamError
from src.domain.usecases.social_login_usecases import PROVIDERS, SocialLoginUsecases

BINDING_COOKIE = "oauth_binding"
COOKIE_PATH = "/api/auth/"
COOKIE_SECONDS = 600
LANGUAGES = ("pt-BR", "en")


def check_provider(provider: str) -> None:
    if provider not in PROVIDERS:
        raise UpstreamError(status.HTTP_404_NOT_FOUND, "not_found")


class SocialLoginController:
    def __init__(self, usecases: SocialLoginUsecases, secure_cookie: bool) -> None:
        self._usecases = usecases
        self._secure_cookie = secure_cookie

    def start(self, provider: str, request: Request) -> RedirectResponse:
        """A top level navigation from the login button, in the same tab (research R2)."""
        check_provider(provider)
        language = request.query_params.get("language")
        result = self._usecases.start(provider, language if language in LANGUAGES else None)
        response = RedirectResponse(result.location, status_code=status.HTTP_302_FOUND)
        # Lax survives the top level return from the provider, also when a phone app opens it.
        response.set_cookie(
            BINDING_COOKIE,
            result.binding,
            max_age=COOKIE_SECONDS,
            path=COOKIE_PATH,
            httponly=True,
            samesite="lax",
            secure=self._secure_cookie,
        )
        return response

    def callback(self, provider: str, request: Request) -> RedirectResponse:
        check_provider(provider)
        query = {name: request.query_params.get(name, "") for name in ("code", "state", "error")}
        location = self._usecases.callback(
            provider, query, request.cookies.get(BINDING_COOKIE), read_client(request)
        )
        response = RedirectResponse(location, status_code=status.HTTP_302_FOUND)
        response.delete_cookie(
            BINDING_COOKIE,
            path=COOKIE_PATH,
            httponly=True,
            samesite="lax",
            secure=self._secure_cookie,
        )
        return response

    def session(self, body: SocialSessionRequestDto) -> LoginResponseDto:
        preferences = body.model_dump(include={"language", "theme"}, exclude_none=True)
        return LoginResponseDto.model_validate(self._usecases.session(body.code, preferences))

    def preview_link(self, body: SocialLinkRequestDto) -> SocialLinkPreviewDto:
        return SocialLinkPreviewDto.model_validate(self._usecases.preview(body.token))

    def confirm_link(self, body: SocialLinkRequestDto) -> Response:
        self._usecases.confirm(body.token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def decline_link(self, body: SocialLinkRequestDto) -> Response:
        self._usecases.decline(body.token)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
