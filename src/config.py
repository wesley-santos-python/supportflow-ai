"""
Configuração centralizada do SupportFlow AI.

Carrega todas as configurações a partir de variáveis de ambiente (arquivo .env),
permitindo trocar banco de dados, modelo de IA e servidor de e-mail sem editar código.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configurações da aplicação carregadas do ambiente."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Banco de dados (troque a URL para SQLite/MySQL/Postgres sem mexer no código)
    # Ex.: postgresql+psycopg://user:pass@host:5432/dbname
    database_url: str = "postgresql+psycopg://supportflow:supportflow@localhost:5432/supportflow"

    # Credenciais de e-mail (IMAP)
    email_user: str | None = None
    email_pass: str | None = None
    imap_server: str = "imap.gmail.com"
    fetch_limit: int = 10

    # Google Gemini
    ai_api_key: str | None = None
    ai_model: str = "gemini-2.5-flash-lite"
    ai_max_body_chars: int = 6000
    ai_max_retries: int = 2

    # Aplicação / logging
    log_level: str = "INFO"
    app_host: str = "127.0.0.1"
    app_port: int = 8000

    @property
    def email_configured(self) -> bool:
        """Indica se as credenciais de e-mail foram preenchidas."""
        return bool(self.email_user and self.email_pass)

    @property
    def ai_configured(self) -> bool:
        """Indica se a API key da IA foi preenchida."""
        return bool(self.ai_api_key)


@lru_cache
def get_settings() -> Settings:
    """Retorna a instância única (cacheada) de configurações."""
    return Settings()


settings = get_settings()
