from fastapi import APIRouter

from src.application.controllers.auth_controller import AuthController, RegistrationController
from src.application.dto.auth_dto import LoginResponseDto, SessionDto, UserDto


def create_auth_route(controller: AuthController) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/auth/login", controller.login, methods=["POST"], response_model=LoginResponseDto
    )
    router.add_api_route(
        "/auth/refresh", controller.refresh, methods=["POST"], response_model=SessionDto
    )
    router.add_api_route(
        "/auth/forgot-password", controller.forgot_password, methods=["POST"], status_code=202
    )
    router.add_api_route(
        "/auth/reset-password", controller.reset_password, methods=["POST"], status_code=204
    )
    router.add_api_route("/users/me", controller.get_me, methods=["GET"], response_model=UserDto)
    router.add_api_route(
        "/users/me/preferences",
        controller.update_preferences,
        methods=["PATCH"],
        response_model=UserDto,
    )
    return router


def create_registration_route(controller: RegistrationController) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/auth/register", controller.register, methods=["POST"], status_code=202)
    router.add_api_route(
        "/auth/verify-email", controller.verify_email, methods=["POST"], status_code=204
    )
    router.add_api_route(
        "/auth/resend-verification",
        controller.resend_verification,
        methods=["POST"],
        status_code=202,
    )
    return router
