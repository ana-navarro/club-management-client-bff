from fastapi import APIRouter

from src.application.controllers.social_login_controller import SocialLoginController
from src.application.dto.auth_dto import LoginResponseDto, SocialLinkPreviewDto


def create_social_login_route(controller: SocialLoginController) -> APIRouter:
    router = APIRouter()
    router.add_api_route("/auth/{provider}/start", controller.start, methods=["GET"])
    router.add_api_route("/auth/{provider}/callback", controller.callback, methods=["GET"])
    router.add_api_route(
        "/auth/social/session",
        controller.session,
        methods=["POST"],
        response_model=LoginResponseDto,
    )
    router.add_api_route(
        "/auth/social/link/preview",
        controller.preview_link,
        methods=["POST"],
        response_model=SocialLinkPreviewDto,
    )
    router.add_api_route(
        "/auth/social/link/confirm", controller.confirm_link, methods=["POST"], status_code=204
    )
    router.add_api_route(
        "/auth/social/link/decline", controller.decline_link, methods=["POST"], status_code=204
    )
    return router
