import pytest
from pydantic import ValidationError
from pydantic_settings import CliApp

from payload_cache.cli.main import CliSettings


def test_parses_all_flags():
    settings = CliApp.run(
        CliSettings,
        cli_args=["--host", "http://x:9", "--repeat", "3", "--json", '{"list_1":["a"],"list_2":["b"]}', "--output", "-"],
    )
    assert settings.host == "http://x:9"
    assert settings.repeat == 3
    assert settings.json_input == '{"list_1":["a"],"list_2":["b"]}'
    assert settings.output == "-"


def test_json_shortcut():
    settings = CliApp.run(CliSettings, cli_args=["--json", '{"list_1":[],"list_2":[]}'])
    assert settings.json_input == '{"list_1":[],"list_2":[]}'


def test_requires_exactly_one_source():
    with pytest.raises(ValidationError):
        CliApp.run(CliSettings, cli_args=[])
    with pytest.raises(ValidationError):
        CliApp.run(CliSettings, cli_args=["--json", "{}", "--input", "f.json"])


def test_repeat_must_be_positive():
    with pytest.raises(ValidationError):
        CliApp.run(CliSettings, cli_args=["--json", "{}", "--repeat", "0"])


def test_help_exits_zero():
    with pytest.raises(SystemExit) as excinfo:
        CliApp.run(CliSettings, cli_args=["--help"])
    assert excinfo.value.code == 0
