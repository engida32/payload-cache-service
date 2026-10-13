"""cache-cli — exercises the service over HTTP.

Parsing/sanitizing uses Pydantic Settings (per the task). The field is
`json_input` (a field literally named `json` would shadow a BaseModel method)
and `cli_shortcuts` exposes it as `--json`.

stdout carries only the payload output (pipe-friendly); the id, cache status and
timing go to stderr. Exit codes: 0 ok, 1 runtime/connection, 2 argument error.
"""

import json as jsonlib
import sys
import time
from pathlib import Path

import httpx
from pydantic import ValidationError, model_validator
from pydantic_settings import BaseSettings, CliApp, SettingsConfigDict

from payload_cache.api.schemas import PayloadRequest


class CliSettings(BaseSettings):
    model_config = SettingsConfigDict(
        cli_shortcuts={"json_input": "json"},
        cli_exit_on_error=True,
    )

    host: str = "http://localhost:8000"
    repeat: int = 1
    input: str | None = None
    json_input: str | None = None
    output: str = "-"

    @model_validator(mode="after")
    def _validate(self) -> "CliSettings":
        if (self.input is None) == (self.json_input is None):
            raise ValueError("provide exactly one of --input or --json")
        if self.repeat < 1:
            raise ValueError("--repeat must be >= 1")
        return self


def _load_payload(settings: CliSettings) -> dict[str, object]:
    if settings.json_input is not None:
        raw = settings.json_input
    elif settings.input == "-":
        raw = sys.stdin.read()
    else:
        assert settings.input is not None
        raw = Path(settings.input).read_text(encoding="utf-8")
    return PayloadRequest.model_validate(jsonlib.loads(raw)).model_dump()


def _emit(settings: CliSettings, lines: list[str]) -> None:
    text = "\n".join(lines) + "\n"
    if settings.output == "-":
        sys.stdout.write(text)
    else:
        Path(settings.output).write_text(text, encoding="utf-8")


def run(settings: CliSettings) -> int:
    try:
        payload = _load_payload(settings)
    except (jsonlib.JSONDecodeError, OSError, ValidationError, AssertionError) as exc:
        print(f"error: invalid input: {exc}", file=sys.stderr)
        return 2

    outputs: list[str] = []
    try:
        with httpx.Client(base_url=settings.host, timeout=10.0) as client:
            for iteration in range(1, settings.repeat + 1):
                started = time.perf_counter()
                created = client.post("/payload", json=payload)
                created.raise_for_status()
                body = created.json()
                fetched = client.get(f"/payload/{body['id']}")
                fetched.raise_for_status()
                elapsed = time.perf_counter() - started
                outputs.append(fetched.json()["output"])
                print(
                    f"[{iteration}/{settings.repeat}] id={body['id']} "
                    f"cached={body['cached']} {elapsed:.3f}s",
                    file=sys.stderr,
                )
    except httpx.HTTPError as exc:
        print(f"error: request failed: {exc}", file=sys.stderr)
        return 1

    _emit(settings, outputs)
    return 0


def main(argv: list[str] | None = None) -> None:
    try:
        settings = CliApp.run(CliSettings, cli_args=argv)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    raise SystemExit(run(settings))


if __name__ == "__main__":
    main()
