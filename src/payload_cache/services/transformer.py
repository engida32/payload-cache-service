"""The 'external service' boundary.

A Protocol keeps the call site honest: the service depends on an interface,
never on the concrete uppercase behaviour, and tests inject a spy to prove how
few times the transformer is actually invoked.
"""

from time import sleep
from typing import Protocol


class Transformer(Protocol):
    def transform(self, value: str) -> str: ...

    def transform_batch(self, values: list[str]) -> list[str]: ...


class UppercaseTransformer:
    """Stand-in for an external service: uppercases with configurable latency."""

    def __init__(self, latency_ms: int = 0) -> None:
        self.latency_ms = latency_ms
        self.call_count = 0

    def transform(self, value: str) -> str:
        self.call_count += 1
        if self.latency_ms > 0:
            sleep(self.latency_ms / 1000)
        return value.upper()

    def transform_batch(self, values: list[str]) -> list[str]:
        return [self.transform(value) for value in values]
