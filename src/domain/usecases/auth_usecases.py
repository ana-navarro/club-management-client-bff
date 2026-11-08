from dataclasses import dataclass

from src.domain.ports.auth_ports import (
    ClientInfo,
    ForgotPasswordPort,
    GetCurrentUserPort,
    JsonObject,
    LoginPort,
    RefreshTokenPort,
    RegisterPort,
    ResendVerificationPort,
    ResetPasswordPort,
    UpdatePreferencesPort,
    UpstreamError,
    VerifyEmailPort,
)

CLIENT_USER_TYPE = "CLIENT"


def save_missing_preferences(
    update_preferences: UpdatePreferencesPort, session: JsonObject, preferences: JsonObject
) -> JsonObject:
    """Saves on the user the session choices it does not have yet, as in the admin login."""
    saved = session["user"]["preferences"]
    missing = {
        name: value
        for name, value in preferences.items()
        if value is not None and saved.get(name) is None
    }
    if not missing:
        return session

    try:
        session["user"] = update_preferences(f"Bearer {session['token']}", missing)
    except UpstreamError:
        # The login is valid. Failing to save a preference must not block it.
        pass
    return session


@dataclass(frozen=True)
class AuthUsecases:
    login_user: LoginPort
    refresh_token: RefreshTokenPort
    forgot_password: ForgotPasswordPort
    reset_password: ResetPasswordPort
    get_current_user: GetCurrentUserPort
    update_preferences: UpdatePreferencesPort

    def login(
        self, email: str, password: str, preferences: JsonObject, client: ClientInfo
    ) -> JsonObject:
        """Logs in as a client and saves the session choices the user does not have."""
        body: JsonObject = {"email": email, "password": password, "userType": CLIENT_USER_TYPE}
        if client.ip:
            body["ip"] = client.ip
        if client.user_agent:
            body["userAgent"] = client.user_agent
        if preferences.get("language"):
            body["language"] = preferences["language"]

        session = self.login_user(body)
        return save_missing_preferences(self.update_preferences, session, preferences)


@dataclass(frozen=True)
class RegistrationUsecases:
    register_client: RegisterPort
    verify_email_link: VerifyEmailPort
    resend_verification_link: ResendVerificationPort

    def register(self, body: JsonObject, client: ClientInfo) -> None:
        """Signs up a client. The address from the gateway feeds the limit per network."""
        request: JsonObject = dict(body)
        if client.ip:
            request["ip"] = client.ip
        self.register_client(request)

    def verify_email(self, body: JsonObject) -> None:
        self.verify_email_link(body)

    def resend_verification(self, body: JsonObject) -> None:
        self.resend_verification_link(body)
