from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

Theme = Literal["light", "dark"]
Language = Literal["pt-BR", "en"]
Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)]


class PreferencesDto(BaseModel):
    theme: Theme | None = None
    language: Language | None = None


class LoginRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    preferences: PreferencesDto = PreferencesDto()


class ForgotPasswordRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    language: Language | None = None


class ResetPasswordRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)
    password: str = Field(min_length=1, max_length=256)


class UpdatePreferencesRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    theme: Theme | None = None
    language: Language | None = None


class ClubDto(BaseModel):
    id: str
    name: str


class UserDto(BaseModel):
    """The user sent to the frontend. Any other field from the service is dropped."""

    id: str
    name: str
    email: str
    type: Literal["ADMIN", "CLIENT"]
    clubs: list[ClubDto]
    preferences: PreferencesDto


class SessionDto(BaseModel):
    token: str
    expiresAt: str  # noqa: N815
    renewAt: str  # noqa: N815


class LoginResponseDto(SessionDto):
    user: UserDto


class RegisterRequestDto(BaseModel):
    """No account type: whoever signs up here is a client."""

    model_config = ConfigDict(extra="forbid")

    name: Name
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)
    language: Language | None = None


class VerifyEmailRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)


class ResendVerificationRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    language: Language | None = None


class SocialSessionRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=512)
    language: Language | None = None
    theme: Theme | None = None


class SocialLinkRequestDto(BaseModel):
    model_config = ConfigDict(extra="forbid")

    token: str = Field(min_length=1, max_length=256)


class SocialLinkPreviewDto(BaseModel):
    """What the confirmation page shows. Any other field from the service is dropped."""

    provider: Literal["google", "facebook"]
    profileName: str  # noqa: N815
    email: str
