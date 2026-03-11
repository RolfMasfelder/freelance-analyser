"""Zentrale Konfiguration — liest Werte aus .env / Umgebungsvariablen."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL
    postgres_user: str = "freelance"
    postgres_password: str = "changeme"
    postgres_db: str = "freelance_analyser"
    database_url: str = (
        "postgresql+psycopg://freelance:changeme@db:5432/freelance_analyser"
    )

    # IMAP
    imap_host: str = "imap.example.com"
    imap_port: int = 993
    imap_user: str = ""
    imap_password: str = ""
    imap_ssl: bool = True

    # Freelancermap
    freelancermap_cookie_browser: str = "firefox"
    freelancermap_user: str = ""
    freelancermap_password: str = ""

    # Logging
    log_level: str = "INFO"
