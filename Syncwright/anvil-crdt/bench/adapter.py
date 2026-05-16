from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Adapter(ABC):
    @abstractmethod
    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def query(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def sync(self, other: "Adapter") -> None:
        raise NotImplementedError

    @abstractmethod
    def snapshot_hash(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def metadata_stats(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def dump_state(self) -> dict[str, Any]:
        raise NotImplementedError

    @abstractmethod
    def close(self) -> None:
        raise NotImplementedError

