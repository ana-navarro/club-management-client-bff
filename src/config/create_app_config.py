from fastapi import FastAPI

from src.application.controllers.get_health_controller import GetHealthController
from src.application.routes.get_health_route import create_get_health_route
from src.domain.usecases.get_health_usecase import GetHealthUsecase


def create_app() -> FastAPI:
    app = FastAPI(title="club-management-client-bff")
    app.include_router(create_get_health_route(GetHealthController(GetHealthUsecase())))
    return app
