from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _parse_csv_ints(raw_value: str | None) -> list[int]:
    if not raw_value or not raw_value.strip():
        return []

    result: list[int] = []
    for item in raw_value.split(","):
        item = item.strip()
        if item:
            result.append(int(item))
    return result


def _parse_optional_int(raw_value: str | None) -> int | None:
    if raw_value is None:
        return None
    raw_value = raw_value.strip()
    if not raw_value:
        return None
    try:
        value = int(raw_value)
        return value or None
    except ValueError:
        return None


@dataclass(frozen=True)
class Settings:
    base_dir: Path = BASE_DIR
    model_dir: Path = BASE_DIR / "data" / "model"
    model_weights_path: Path = BASE_DIR / "data" / "model" / "best_model_indobert_optimized.pt"
    thresholds_path: Path = BASE_DIR / "data" / "model" / "optimal_thresholds_final.json"
    kamusalay_path: Path = BASE_DIR / "data" / "dataset_raw" / "new_kamusalay.csv"

    # API Settings
    api_host: str = os.getenv("API_HOST", "127.0.0.1")
    api_port: int = int(os.getenv("API_PORT", "8000"))
    api_url: str = os.getenv("API_URL", "http://127.0.0.1:8000")

    # Discord Bot Settings
    discord_bot_token: str = os.getenv("DISCORD_BOT_TOKEN") or os.getenv("DISCORD_TOKEN", "")
    discord_guild_id: int | None = _parse_optional_int(os.getenv("DISCORD_GUILD_ID"))
    discord_allowed_channel_ids: list[int] = None  # type: ignore[assignment]
    discord_admin_log_channel_id: int | None = _parse_optional_int(
        os.getenv("DISCORD_ADMIN_LOG_CHANNEL_ID")
    )

    # Dashboard & Database Settings
    flask_host: str = os.getenv("FLASK_HOST", "0.0.0.0")
    flask_port: int = int(os.getenv("FLASK_PORT", "5000"))
    database_path: Path = BASE_DIR / os.getenv("DATABASE_PATH", "app.db")
    run_mode: str = os.getenv("RUN_MODE", "all").lower().strip()
    dashboard_debug: bool = os.getenv("DASHBOARD_DEBUG", "true").lower() == "true"
    warning_delete_after_seconds: int = int(os.getenv("WARNING_DELETE_AFTER_SECONDS", "10"))
    kick_violation_threshold: int = int(
        os.getenv("KICK_VIOLATION_THRESHOLD", os.getenv("KICK_STRIKE_THRESHOLD", "3"))
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "discord_allowed_channel_ids",
            _parse_csv_ints(os.getenv("DISCORD_ALLOWED_CHANNEL_IDS", "")),
        )


settings = Settings()
