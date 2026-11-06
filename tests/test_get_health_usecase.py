from src.domain.usecases.get_health_usecase import GetHealthUsecase


def test_reports_the_service_as_ok() -> None:
    assert GetHealthUsecase().execute().status == "ok"
