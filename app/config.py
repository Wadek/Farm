from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./data/farm.db"
    anthropic_api_key: str = ""
    secret_key: str = "changeme"

    # Default node coordinates — Korpiharjuntie, Yli-Solttila, Hyvinkää
    # Road centroid from OSM; exact GPS for #363 pending phone integration
    default_lat: float = 60.5522
    default_lng: float = 24.7050


settings = Settings()
