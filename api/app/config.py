from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://hangry:hangry@localhost:5433/hangry"

    # Under pytest each test gets its own event loop, and a pooled asyncpg
    # connection is bound to the loop that opened it. Pooling is disabled
    # there so connections never outlive their loop.
    testing: bool = False

    # Overpass is free but slow and rate-limited. It is never called on the
    # request path when the geohash tile is fresh — see osm.py.
    overpass_url: str = "https://overpass-api.de/api/interpreter"
    overpass_timeout_s: float = 30.0
    tile_ttl_days: int = 30

    session_ttl_hours: int = 24
    candidate_target: int = 8
    candidate_minimum: int = 3

    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
