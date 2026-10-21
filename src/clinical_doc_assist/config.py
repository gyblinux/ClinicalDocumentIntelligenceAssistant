"""Environment-backed application configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

DEFAULT_BASE_URL = "https://api.deepseek.com"
DEFAULT_MODEL = "deepseek-flash"
DEFAULT_MAX_STEPS = 8


class SettingsError(ValueError):
    """Raised when application settings are missing or invalid."""


@dataclass(frozen=True, slots=True)
class Settings:
    """Configuration needed to call a DeepSeek-compatible API."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    model: str = DEFAULT_MODEL
    max_steps: int = DEFAULT_MAX_STEPS

    @classmethod
    def from_env(cls, *, load_env_file: bool = True) -> Settings:
        """Build settings from environment variables.

        A dedicated DeepSeek key is required on purpose. Falling back to an
        OpenAI key here could disclose that credential to another provider.
        """

        if load_env_file:
            load_dotenv()

        api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if not api_key:
            raise SettingsError(
                "DEEPSEEK_API_KEY is not set. Copy .env.example to .env and add "
                "your DeepSeek API key."
            )

        base_url = os.getenv("DEEPSEEK_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/")
        if not base_url.startswith(("https://", "http://")):
            raise SettingsError("DEEPSEEK_BASE_URL must start with http:// or https://.")

        model = os.getenv("DEEPSEEK_MODEL", DEFAULT_MODEL).strip()
        if not model:
            raise SettingsError("DEEPSEEK_MODEL cannot be empty.")

        raw_max_steps = os.getenv("AGENT_MAX_STEPS", str(DEFAULT_MAX_STEPS)).strip()
        try:
            max_steps = int(raw_max_steps)
        except ValueError as exc:
            raise SettingsError("AGENT_MAX_STEPS must be an integer.") from exc
        if max_steps < 1:
            raise SettingsError("AGENT_MAX_STEPS must be at least 1.")

        return cls(
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_steps=max_steps,
        )

