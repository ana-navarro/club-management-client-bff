from fastapi import APIRouter

from src.application.controllers.get_health_controller import GetHealthController
from src.application.dto.get_health_dto import GetHealthResponseDto


def create_get_health_route(controller: GetHealthController) -> APIRouter:
    router = APIRouter()
    router.add_api_route(
        "/health", controller.handle, methods=["GET"], response_model=GetHealthResponseDto
    )
    return router
