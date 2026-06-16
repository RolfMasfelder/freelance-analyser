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
    imap_port: int = 143
    imap_ssl: bool = False
    imap_starttls: bool = True

    # Freelancermap
    freelancermap_cookie_browser: str = "firefox"
    freelancermap_user: str = ""
    freelancermap_password: str = ""

    # CV-Datei
    cv_path: str = "data/cv.yaml"

    # LLM — Antwortschreiben-Generierung (LM Studio auf zweitem Rechner)
    llm_base_url: str = "http://192.168.178.80:1234/v1"
    llm_api_key: str = "lm-studio"  # LM Studio braucht keinen echten Key
    llm_model: str = "zai-org/glm-4.7-flash"
    llm_timeout: int = 120

    # Logging
    log_level: str = "INFO"
