from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./data/farm.db"
    anthropic_api_key: str = ""
    secret_key: str = "changeme"


settings = Settings()
