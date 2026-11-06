from src.domain.ports.get_health_input_port import Health


class GetHealthUsecase:
    def execute(self) -> Health:
        return Health(status="ok")
