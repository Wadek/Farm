from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    database_url: str = "sqlite:///./data/farm.db"
    anthropic_api_key: str = ""
    secret_key: str = "changeme"

    # Default node coordinates — Korpiharjuntie, Yli-Solttila, Hyvinkää
    default_lat: float = 60.5522
    default_lng: float = 24.7050

    # Ruuvi Cloud (https://ruuvi.com — create account, sync tag)
    ruuvi_email: str = ""
    ruuvi_password: str = ""

    # Ajax Systems Cloud (request access at ajax.systems/api-request/)
    ajax_email: str = ""
    ajax_password: str = ""

    public_base_url: str = "http://127.0.0.1:8791"
    sms_provider: str = "log"
    sms_from: str = "Satokori"
    elks_username: str = ""
    elks_password: str = ""
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""


settings = Settings()
