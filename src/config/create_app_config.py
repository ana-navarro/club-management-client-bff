import os
from collections.abc import AsyncIterator, Callable, Mapping
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from src.application.controllers.auth_controller import AuthController, RegistrationController
from src.application.controllers.get_health_controller import GetHealthController
from src.application.controllers.social_login_controller import SocialLoginController
from src.application.routes.auth_route import create_auth_route, create_registration_route
from src.application.routes.get_health_route import create_get_health_route
from src.application.routes.social_login_route import create_social_login_route
from src.config.create_http_client_config import get_http_client
from src.domain.ports.auth_ports import UpstreamError
from src.domain.usecases.auth_usecases import AuthUsecases, RegistrationUsecases
from src.domain.usecases.get_health_usecase import GetHealthUsecase
from src.domain.usecases.social_login_usecases import SocialLoginUsecases
from src.infra.adapters.users_svc_adapters import (
    ForgotPasswordAdapter,
    GetCurrentUserAdapter,
    LoginAdapter,
    RefreshTokenAdapter,
    RegisterAdapter,
    ResendVerificationAdapter,
    ResetPasswordAdapter,
    SocialAuthorizationAdapter,
    SocialCallbackAdapter,
    SocialLinkConfirmAdapter,
    SocialLinkDeclineAdapter,
    SocialLinkPreviewAdapter,
    SocialSessionAdapter,
    UpdatePreferencesAdapter,
    VerifyEmailAdapter,
)


@asynccontextmanager
async def check_configuration(_: FastAPI) -> AsyncIterator[None]:
    get_http_client()
    yield


def handle_upstream_error(_: Request, error: Exception) -> JSONResponse:
    assert isinstance(error, UpstreamError)
    return JSONResponse(status_code=error.status_code, content={"error": error.code})


def handle_validation_error(_: Request, __: Exception) -> JSONResponse:
    # The default answer repeats the input, which may contain a password.
    return JSONResponse(status_code=400, content={"error": "invalid_request"})


def create_app(
    http_client: Callable[[], httpx.Client] = get_http_client,
    env: Mapping[str, str] = os.environ,
) -> FastAPI:
    app = FastAPI(
        title="club-management-client-bff",
        lifespan=check_configuration,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
    )
    usecases = AuthUsecases(
        login_user=LoginAdapter(http_client),
        refresh_token=RefreshTokenAdapter(http_client),
        forgot_password=ForgotPasswordAdapter(http_client),
        reset_password=ResetPasswordAdapter(http_client),
        get_current_user=GetCurrentUserAdapter(http_client),
        update_preferences=UpdatePreferencesAdapter(http_client),
    )
    app.add_exception_handler(UpstreamError, handle_upstream_error)
    app.add_exception_handler(RequestValidationError, handle_validation_error)
    app.include_router(create_get_health_route(GetHealthController(GetHealthUsecase())))
    app.include_router(create_auth_route(AuthController(usecases)))
    registration = RegistrationUsecases(
        register_client=RegisterAdapter(http_client),
        verify_email_link=VerifyEmailAdapter(http_client),
        resend_verification_link=ResendVerificationAdapter(http_client),
    )
    app.include_router(create_registration_route(RegistrationController(registration)))
    social = SocialLoginUsecases(
        authorize=SocialAuthorizationAdapter(http_client),
        complete=SocialCallbackAdapter(http_client),
        exchange_code=SocialSessionAdapter(http_client),
        preview_link=SocialLinkPreviewAdapter(http_client),
        confirm_link=SocialLinkConfirmAdapter(http_client),
        decline_link=SocialLinkDeclineAdapter(http_client),
        update_preferences=UpdatePreferencesAdapter(http_client),
    )
    # The binding cookie is Secure whenever the client app is served over HTTPS.
    secure_cookie = env.get("CLIENT_APP_URL", "").startswith("https://")
    app.include_router(create_social_login_route(SocialLoginController(social, secure_cookie)))
    return app
