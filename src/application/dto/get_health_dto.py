from typing import Literal

from pydantic import BaseModel


class GetHealthResponseDto(BaseModel):
    status: Literal["ok"]
