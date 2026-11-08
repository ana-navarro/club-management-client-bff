from typing import Any

import pytest

from src.domain.ports.auth_ports import ClientInfo, JsonObject, UpstreamError
from src.domain.usecases.auth_usecases import AuthUsecases


def make_session(theme: str | None = None, language: str | None = None) -> JsonObject:
    return {
        "token": "jwt",
        "user": {"id": "u1", "preferences": {"theme": theme, "language": language}},
    }


class Fakes:
    def __init__(self, session: JsonObject) -> None:
        self.session = session
        self.login_body: JsonObject = {}
        self.updates: list[tuple[str, JsonObject]] = []
        self.fail_update = False

    def login(self, body: JsonObject) -> JsonObject:
        self.login_body = body
        return self.session

    def update(self, authorization: str, body: JsonObject) -> JsonObject:
        if self.fail_update:
            raise UpstreamError(500, "internal_error")
        self.updates.append((authorization, body))
        return {"id": "u1", "preferences": {"theme": body.get("theme"), "language": None}}

    def usecases(self) -> AuthUsecases:
        unused: Any = None
        return AuthUsecases(
            login_user=self.login,
            refresh_token=unused,
            forgot_password=unused,
            reset_password=unused,
            get_current_user=unused,
            update_preferences=self.update,
        )


CLIENT = ClientInfo(ip="1.2.3.4", user_agent="Firefox")


def test_logs_in_as_client_with_the_client_data() -> None:
    fakes = Fakes(make_session())

    fakes.usecases().login("a@b.c", "secret", {"language": "pt-BR"}, CLIENT)

    assert fakes.login_body == {
        "email": "a@b.c",
        "password": "secret",
        "userType": "CLIENT",
        "ip": "1.2.3.4",
        "userAgent": "Firefox",
        "language": "pt-BR",
    }


def test_leaves_out_unknown_client_data() -> None:
    fakes = Fakes(make_session())

    fakes.usecases().login("a@b.c", "secret", {}, ClientInfo(ip=None, user_agent=None))

    assert fakes.login_body == {"email": "a@b.c", "password": "secret", "userType": "CLIENT"}


def test_saves_session_choices_the_user_does_not_have() -> None:
    fakes = Fakes(make_session())

    result = fakes.usecases().login("a@b.c", "secret", {"theme": "dark"}, CLIENT)

    assert fakes.updates == [("Bearer jwt", {"theme": "dark"})]
    assert result["user"]["preferences"]["theme"] == "dark"


def test_saved_choices_win_over_the_session() -> None:
    fakes = Fakes(make_session(theme="light", language="en"))

    result = fakes.usecases().login(
        "a@b.c", "secret", {"theme": "dark", "language": "pt-BR"}, CLIENT
    )

    assert fakes.updates == []
    assert result["user"]["preferences"] == {"theme": "light", "language": "en"}


def test_saves_only_the_missing_choice() -> None:
    fakes = Fakes(make_session(theme="light"))

    fakes.usecases().login("a@b.c", "secret", {"theme": "dark", "language": "en"}, CLIENT)

    assert fakes.updates == [("Bearer jwt", {"language": "en"})]


@pytest.mark.parametrize("value", [None])
def test_ignores_empty_choices(value: None) -> None:
    fakes = Fakes(make_session())

    fakes.usecases().login("a@b.c", "secret", {"theme": value}, CLIENT)

    assert fakes.updates == []


def test_login_survives_a_failure_saving_choices() -> None:
    fakes = Fakes(make_session())
    fakes.fail_update = True

    result = fakes.usecases().login("a@b.c", "secret", {"theme": "dark"}, CLIENT)

    assert result["token"] == "jwt"
