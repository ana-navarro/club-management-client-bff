from src.application.dto.get_health_dto import GetHealthResponseDto
from src.domain.ports.get_health_input_port import GetHealthInputPort


class GetHealthController:
    def __init__(self, usecase: GetHealthInputPort) -> None:
        self._usecase = usecase

    def handle(self) -> GetHealthResponseDto:
        return GetHealthResponseDto(status=self._usecase.execute().status)
