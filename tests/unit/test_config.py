import pytest
from pydantic import ValidationError

from querywise.config import Settings, get_settings


def test_settings_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verifica valores por defecto y cadenas DSN sin depender de un archivo .env local."""
    monkeypatch.delenv("OLLAMA_MODEL", raising=False)
    monkeypatch.delenv("POSTGRES_DB", raising=False)

    settings = Settings(_env_file=None)

    assert settings.ollama_model == "qwen2.5-coder:7b"
    assert settings.postgres_db == "querywise"
    assert settings.sql_max_rows == 100
    assert (
        settings.readonly_dsn
        == "postgresql://querywise_ro:change_me_ro@localhost:5432/querywise"
    )
    assert (
        settings.admin_dsn
        == "postgresql://postgres:change_me_admin@localhost:5432/querywise"
    )


def test_settings_rejects_invalid_guardrails() -> None:
    """Asegura que los límites de seguridad fallen rápido si reciben valores inseguros."""
    with pytest.raises(ValidationError):
        Settings(_env_file=None, sql_max_rows=0)

    with pytest.raises(ValidationError):
        Settings(_env_file=None, sql_statement_timeout_ms=10)


def test_get_settings_is_cached() -> None:
    """Confirma que get_settings devuelve siempre la misma instancia cacheada."""
    get_settings.cache_clear()
    first = get_settings()
    second = get_settings()
    assert first is second