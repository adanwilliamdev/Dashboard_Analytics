"""Configuracoes centralizadas da aplicacao."""
from typing import List
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_WEAK_SECRET_MARKERS = ("dev_secret", "sua_chave", "change", "troque", "secret_key")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_ENV: str = "development"  # development | test | production
    SECRET_KEY: str = "dev_secret_key_change_me"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    DATABASE_URL: str = "sqlite:///./dashboard.db"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_BASE_URL: str = "http://localhost:8000"

    # Origens permitidas (separadas por virgula)
    CORS_ORIGINS: str = "http://localhost:8501,http://127.0.0.1:8501"

    # Cache (em memoria por padrao; Redis se REDIS_URL estiver definido). 0 = desligado
    CACHE_TTL_SECONDS: int = 30
    REDIS_URL: str = ""

    # DESCONTINUADO e ignorado: promover por cadastro permitia que qualquer pessoa tomasse o
    # username reservado. Crie o primeiro admin com `python -m app.cli create-admin`.
    ADMIN_USERNAMES: str = ""

    # Fuso do "dia do usuario": define hoje, janelas de dias, mes do orcamento e datas padrao
    APP_TIMEZONE: str = "America/Sao_Paulo"

    # Nivel dos logs da aplicacao (logger "dashboard.*")
    LOG_LEVEL: str = "INFO"

    # Em producao deixe false e use `alembic upgrade head`
    AUTO_CREATE_TABLES: bool = True

    # Protecao contra forca bruta no login
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_WINDOW_SECONDS: int = 300

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"

    @model_validator(mode="after")
    def _validate_timezone(self) -> "Settings":
        try:
            ZoneInfo(self.APP_TIMEZONE)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"APP_TIMEZONE invalido: {self.APP_TIMEZONE!r} (ex.: America/Sao_Paulo)") from exc
        return self

    @model_validator(mode="after")
    def _validate_production_secret(self) -> "Settings":
        if self.is_production:
            weak = len(self.SECRET_KEY) < 32 or any(
                m in self.SECRET_KEY.lower() for m in _WEAK_SECRET_MARKERS
            )
            if weak:
                raise ValueError(
                    "SECRET_KEY fraca para APP_ENV=production. Gere uma com: "
                    'python -c "import secrets; print(secrets.token_urlsafe(48))"'
                )
        return self


settings = Settings()
