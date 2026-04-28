from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "evociv"
    debug: bool = True
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    tick_rate: float = 0.1  # seconds per tick (10 ticks/sec)
    database_url: str = "sqlite+aiosqlite:///./evociv.db"

    model_config = {"env_prefix": "EVOCIV_", "env_file": ".env"}


settings = Settings()
