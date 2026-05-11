from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+psycopg://tw:tw@localhost:5432/tenderwatch"
    redis_url: str = "redis://localhost:6379/0"
    session_secret: str = "dev-secret-change-me"

    anthropic_api_key: str = ""
    openai_api_key: str = ""

    line_login_channel_id: str = ""
    line_login_channel_secret: str = ""
    line_login_redirect_uri: str = ""
    line_bot_channel_access_token: str = ""
    line_bot_channel_secret: str = ""

    ecpay_merchant_id: str = ""
    ecpay_hash_key: str = ""
    ecpay_hash_iv: str = ""
    ecpay_return_url: str = ""
    ecpay_client_back_url: str = ""
    ecpay_invoice_api_key: str = ""

    resend_api_key: str = ""
    sentry_dsn: str = ""
    betterstack_heartbeat_url: str = ""

    pcc_opendata_base_url: str = "https://web.pcc.gov.tw"
    semantic_sim_threshold: float = 0.30
    env: str = "dev"


def get_settings() -> Settings:
    return Settings()
