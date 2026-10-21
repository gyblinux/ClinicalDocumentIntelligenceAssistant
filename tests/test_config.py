from __future__ import annotations

import pytest

from clinical_doc_assist.config import Settings, SettingsError


def test_settings_load_expected_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("DEEPSEEK_BASE_URL", "https://example.test/v1/")
    monkeypatch.setenv("DEEPSEEK_MODEL", "test-model")
    monkeypatch.setenv("AGENT_MAX_STEPS", "4")

    settings = Settings.from_env(load_env_file=False)

    assert settings.api_key == "test-key"
    assert settings.base_url == "https://example.test/v1"
    assert settings.model == "test-model"
    assert settings.max_steps == 4


def test_settings_require_dedicated_deepseek_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-be-reused")

    with pytest.raises(SettingsError, match="DEEPSEEK_API_KEY"):
        Settings.from_env(load_env_file=False)


def test_settings_reject_invalid_max_steps(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    monkeypatch.setenv("AGENT_MAX_STEPS", "0")

    with pytest.raises(SettingsError, match="at least 1"):
        Settings.from_env(load_env_file=False)

