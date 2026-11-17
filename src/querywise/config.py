from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuración de la aplicación cargada desde variables de entorno o archivo .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM (Ollama local)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5-coder:7b"

    # PostgreSQL
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "querywise"
    postgres_admin_user: str = "postgres"
    postgres_admin_password: str = "change_me_admin"
    postgres_readonly_user: str = "querywise_ro"
    postgres_readonly_password: str = "change_me_ro"

    # Seguridad y límites de ejecución
    sql_max_rows: int = Field(default=100, ge=1, le=1000)
    sql_statement_timeout_ms: int = Field(default=5000, ge=100, le=60000)
    sql_max_explain_cost: float = Field(default=10000.0, gt=0)

    @property
    def readonly_dsn(self) -> str:
        """Cadena de conexión a PostgreSQL usando el rol restringido de solo lectura."""
        return (
            f"postgresql://{self.postgres_readonly_user}:{self.postgres_readonly_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def admin_dsn(self) -> str:
        """Cadena de conexión a PostgreSQL usando el rol administrador (solo scripts de carga)."""
        return (
            f"postgresql://{self.postgres_admin_user}:{self.postgres_admin_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Devuelve una instancia cacheada de Settings para evitar releer .env en cada llamada."""
    return Settings()
