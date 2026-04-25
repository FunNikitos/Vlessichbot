"""Application configuration loaded from .env via pydantic-settings."""
from __future__ import annotations

from typing import List

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ----- Telegram -----
    bot_token: str = ""
    owner_id: int = 0
    run_mode: str = "polling"  # polling | webhook
    webhook_url: str = ""
    webhook_secret: str = ""

    # ----- Database / Redis -----
    database_url: str = "postgresql+asyncpg://vlessich:vlessich@localhost:5432/vlessich"
    redis_url: str = "redis://localhost:6379/0"

    # ----- Marzban -----
    marzban_api_url: str = "http://localhost:8000"
    marzban_username: str = "admin"
    marzban_password: str = ""
    marzban_token_ttl_min: int = 1440

    # ----- Server / domain -----
    server_domain: str = "vpn.example.com"
    server_ip: str = ""
    subscription_public_port: int = 443
    sub_host: str = "0.0.0.0"
    sub_port: int = 8081

    # ----- Reality / SNI -----
    sni_donors: List[str] = Field(
        default_factory=lambda: ["www.microsoft.com", "www.cloudflare.com", "github.com"]
    )
    short_id_rotation_days: int = 7

    # ----- Honeypot -----
    honeypot_enabled: bool = True
    honeypot_port: int = 8080

    # ----- Monitoring -----
    monitor_interval_min: int = 10
    expiration_interval_min: int = 5
    antifilter_refresh_hours: int = 24
    antifilter_url: str = "https://antifilter.download/list/subnet.lst"

    # ----- Bot business rules -----
    trial_enabled: bool = True
    trial_duration_hours: int = 24
    max_connections_trial: int = 1
    max_connections_code: int = 5

    # ----- Antispam -----
    rate_limit_max: int = 5
    rate_limit_window_sec: int = 10
    auth_max_attempts: int = 3
    auth_block_minutes: int = 15

    @field_validator("sni_donors", mode="before")
    @classmethod
    def _split_csv(cls, v):
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v


settings = Settings()
