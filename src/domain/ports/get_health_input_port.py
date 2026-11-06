from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class Health:
    status: Literal["ok"]


class GetHealthInputPort(Protocol):
    def execute(self) -> Health: ...
