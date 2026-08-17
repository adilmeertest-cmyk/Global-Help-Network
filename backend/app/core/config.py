from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    test_database_url: str = ""
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7
    cors_origins: str = ""
    log_level: str = "INFO"
    environment: str = "development"

    @property
    def normalized_database_url(self) -> str:
        """Return a URL that SQLAlchemy's asyncpg driver can consume.

        Cloud providers commonly expose DATABASE_URL as postgres:// or
        postgresql://. The application uses asyncpg, so those URLs must use
        the async dialect. We also translate the common sslmode=require
        query parameter into asyncpg's ssl=require form.
        """
        raw = self.database_url.strip()
        if not raw:
            raise ValueError("DATABASE_URL is required")

        parts = urlsplit(raw)
        scheme = parts.scheme
        if scheme in {"postgres", "postgresql"}:
            scheme = "postgresql+asyncpg"
        elif scheme != "postgresql+asyncpg":
            raise ValueError("DATABASE_URL must use postgres://, postgresql://, or postgresql+asyncpg://")

        query = parse_qsl(parts.query, keep_blank_values=True)
        cleaned: list[tuple[str, str]] = []
        ssl_value = None
        for key, value in query:
            if key == "sslmode":
                if value in {"require", "verify-ca", "verify-full"}:
                    ssl_value = "require"
                continue
            cleaned.append((key, value))
        if ssl_value:
            cleaned.append(("ssl", ssl_value))

        return urlunsplit((scheme, parts.netloc, parts.path, urlencode(cleaned), parts.fragment))


settings = Settings()
