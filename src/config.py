"""Zentrale Konfiguration — liest Werte aus .env / Umgebungsvariablen."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # PostgreSQL — Pflichtfeld, muss in .env gesetzt sein
    database_url: str

    # IMAP — Pflichtfelder für Live-Abruf; bei --no-imap nicht benötigt
    imap_host: str
    imap_user: str
    imap_password: str
    imap_port: int = 993
    imap_ssl: bool = True

    # Freelancermap
    freelancermap_cookie_browser: str = "firefox"
    freelancermap_user: str = ""
    freelancermap_password: str = ""

    # Logging
    log_level: str = "INFO"
