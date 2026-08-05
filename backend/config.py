import os
from dataclasses import dataclass


PLACEHOLDER_VALUES = {
    "",
    "change-me",
    "replace-me",
    "replace-with-a-secure-random-key",
    "replace-with-a-secure-random-secret-at-least-32-characters",
}


@dataclass(frozen=True)
class Settings:
    environment: str
    database_url: str
    agent_api_key: str
    jwt_secret: str

    @property
    def is_production(self) -> bool:
        return self.environment == "production"


def require_value(name: str) -> str:
    value = os.getenv(name, "").strip()

    if value.lower() in PLACEHOLDER_VALUES:
        raise RuntimeError(f"{name} is missing or still contains a placeholder value.")

    return value


def load_settings() -> Settings:
    environment = os.getenv("WATCHTOWER_ENV", "development").strip().lower()

    settings = Settings(
        environment=environment,
        database_url=require_value("WATCHTOWER_DATABASE_URL"),
        agent_api_key=require_value("WATCHTOWER_AGENT_API_KEY"),
        jwt_secret=require_value("WATCHTOWER_JWT_SECRET"),
    )

    if len(settings.agent_api_key) < 32:
        raise RuntimeError("WATCHTOWER_AGENT_API_KEY must contain at least 32 characters.")

    if len(settings.jwt_secret) < 32:
        raise RuntimeError("WATCHTOWER_JWT_SECRET must contain at least 32 characters.")

    if settings.is_production and settings.database_url.startswith("sqlite"):
        raise RuntimeError("Production cannot use SQLite. Configure PostgreSQL.")

    return settings