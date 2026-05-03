from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "evociv"
    debug: bool = True
    ws_host: str = "0.0.0.0"
    ws_port: int = 8765
    tick_rate: float = 0.1  # seconds per tick (10 ticks/sec)
    database_url: str = "sqlite+aiosqlite:///./evociv.db"

    # LLM settings
    llm_enabled: bool = True
    llm_model: str = "mistral"
    llm_base_url: str = "http://localhost:11434"
    llm_timeout: int = 60  # seconds (first call is slow due to Ollama cold start)
    llm_fallback_to_mock: bool = True  # Use mock if real LLM fails

    model_config = {"env_prefix": "EVOCIV_", "env_file": ".env"}


settings = Settings()
