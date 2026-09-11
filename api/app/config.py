from pydantic_settings import BaseSettings, SettingsConfigDict

from app.dburl import normalize


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # As the host hands it over. Providers emit libpq strings, which need
    # translating before asyncpg will take them. See app/dburl.py.
    database_url: str = "postgresql+asyncpg://hangry:hangry@localhost:5433/hangry"

    @property
    def sqlalchemy_url(self) -> str:
        """`database_url` with the async driver and no libpq-only query string."""
        return normalize(self.database_url)[0]

    @property
    def sqlalchemy_connect_args(self) -> dict:
        """What the query string became, in the form asyncpg wants."""
        return normalize(self.database_url)[1]

    # Under pytest each test gets its own event loop, and a pooled asyncpg
    # connection is bound to the loop that opened it. Pooling is disabled
    # there so connections never outlive their loop.
    testing: bool = False

    # Overpass is free but slow and rate-limited. It is never called on the
    # request path when the geohash tile is fresh, see osm.py.
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_s: float = 30.0
    tile_ttl_days: int = 30

    session_ttl_hours: int = 24

    # Retention. The interface promises rounds delete themselves, so a sweep
    # runs in-process and makes that true. See app/retention.py.
    purge_enabled: bool = True
    purge_interval_minutes: int = 60
    group_retention_days: int = 90

    candidate_target: int = 8
    candidate_minimum: int = 3

    log_level: str = "INFO"

    # Comma-separated. The browser talks to this API cross-origin, so a
    # forgotten production origin here looks exactly like the API being down.
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
