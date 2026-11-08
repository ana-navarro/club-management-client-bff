from fastapi import Request, Response, status

from src.application.dto.auth_dto import (
    ForgotPasswordRequestDto,
    LoginRequestDto,
    LoginResponseDto,
    RegisterRequestDto,
    ResendVerificationRequestDto,
    ResetPasswordRequestDto,
    SessionDto,
    UpdatePreferencesRequestDto,
    UserDto,
    VerifyEmailRequestDto,
)
from src.domain.ports.auth_ports import ClientInfo, UpstreamError
from src.domain.usecases.auth_usecases import AuthUsecases, RegistrationUsecases


def read_authorization(request: Request) -> str:
    authorization = request.headers.get("authorization")
    if not authorization:
        raise UpstreamError(status.HTTP_401_UNAUTHORIZED, "invalid_token")
    return authorization


def read_client(request: Request) -> ClientInfo:
    return ClientInfo(
        ip=request.headers.get("x-real-ip"),
        user_agent=request.headers.get("user-agent"),
    )


class AuthController:
    def __init__(self, usecases: AuthUsecases) -> None:
        self._usecases = usecases

    def login(self, body: LoginRequestDto, request: Request) -> LoginResponseDto:
        session = self._usecases.login(
            body.email,
            body.password,
            body.preferences.model_dump(exclude_none=True),
            read_client(request),
        )
        return LoginResponseDto.model_validate(session)

    def refresh(self, request: Request) -> SessionDto:
        session = self._usecases.refresh_token(read_authorization(request))
        return SessionDto.model_validate(session)

    def forgot_password(self, body: ForgotPasswordRequestDto) -> Response:
        self._usecases.forgot_password(body.model_dump(exclude_none=True))
        return Response(status_code=status.HTTP_202_ACCEPTED)

    def reset_password(self, body: ResetPasswordRequestDto) -> Response:
        self._usecases.reset_password(body.model_dump())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def get_me(self, request: Request) -> UserDto:
        return UserDto.model_validate(self._usecases.get_current_user(read_authorization(request)))

    def update_preferences(self, body: UpdatePreferencesRequestDto, request: Request) -> UserDto:
        user = self._usecases.update_preferences(
            read_authorization(request), body.model_dump(exclude_none=True)
        )
        return UserDto.model_validate(user)


class RegistrationController:
    def __init__(self, usecases: RegistrationUsecases) -> None:
        self._usecases = usecases

    def register(self, body: RegisterRequestDto, request: Request) -> Response:
        self._usecases.register(body.model_dump(exclude_none=True), read_client(request))
        return Response(status_code=status.HTTP_202_ACCEPTED)

    def verify_email(self, body: VerifyEmailRequestDto) -> Response:
        self._usecases.verify_email(body.model_dump())
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    def resend_verification(self, body: ResendVerificationRequestDto) -> Response:
        self._usecases.resend_verification(body.model_dump(exclude_none=True))
        return Response(status_code=status.HTTP_202_ACCEPTED)
