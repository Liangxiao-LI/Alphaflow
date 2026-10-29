from __future__ import annotations

from pathlib import Path

import pytest

from alphaflow.config import MissingApiKeyError, load_dotenv, load_settings


def test_missing_key_is_allowed_until_required():
    settings = load_settings({})
    assert settings.nasdaq_api_key is None
    assert settings.data_dir == Path("./data")
    with pytest.raises(MissingApiKeyError):
        settings.require_api_key()


def test_key_never_appears_in_repr():
    settings = load_settings({"NASDAQ_API_KEY": "synthetic-secret-123"})
    assert settings.require_api_key() == "synthetic-secret-123"
    assert "synthetic-secret-123" not in repr(settings)


def test_dotenv_parsing_and_env_precedence(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("# comment\nNASDAQ_API_KEY='from-file'\nALPHAFLOW_LOG_LEVEL=debug\n")
    monkeypatch.delenv("NASDAQ_API_KEY", raising=False)
    monkeypatch.setenv("ALPHAFLOW_LOG_LEVEL", "warning")
    settings = load_settings(load_dotenv(env_file))
    assert settings.nasdaq_api_key == "from-file"
    assert settings.log_level == "WARNING"
