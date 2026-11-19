"""Run one call per key while concurrent callers wait for its result.

Without this, two simultaneous requests for the same payload both transform the
same strings. The map holds only in-flight keys, so memory follows concurrency
rather than traffic.
"""

from collections.abc import Callable
from threading import Event, Lock
from typing import TypeVar, cast

T = TypeVar("T")


class _Flight:
    __slots__ = ("done", "error", "value", "waiters")

    def __init__(self) -> None:
        self.done = Event()
        self.error: BaseException | None = None
        self.value: object | None = None
        self.waiters = 0


class SingleFlight:
    def __init__(self) -> None:
        self._lock = Lock()
        self._flights: dict[str, _Flight] = {}

    def run(self, key: str, fn: Callable[[], T]) -> tuple[T, bool]:
        """Return (value, leader). The leader runs ``fn``; waiters share its result."""
        with self._lock:
            flight = self._flights.get(key)
            leader = flight is None
            if flight is None:
                flight = _Flight()
                self._flights[key] = flight
            flight.waiters += 1

        if not leader:
            flight.done.wait()
            self._leave(key, flight)
            if flight.error is not None:
                raise flight.error
            return cast(T, flight.value), False

        try:
            flight.value = fn()
            return cast(T, flight.value), True
        except BaseException as exc:
            flight.error = exc
            raise
        finally:
            flight.done.set()
            self._leave(key, flight)

    def _leave(self, key: str, flight: _Flight) -> None:
        with self._lock:
            flight.waiters -= 1
            if flight.waiters == 0:
                self._flights.pop(key, None)
