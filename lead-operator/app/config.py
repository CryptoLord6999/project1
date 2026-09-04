from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Telegram
    telegram_bot_token: str
    
    # WhatsApp Green API
    green_api_id: str
    green_api_token: str
    
    # LLM (DashScope)
    dashscope_api_key: str
    
    # Database
    database_url: str = "postgresql://postgres:postgres@db:5432/lead_operator"
    
    # Redis
    redis_url: str = "redis://redis:6379/0"
    
    # Owner notifications
    owner_telegram_id: int
    
    # App settings
    app_env: str = "development"
    log_level: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = False


settings = Settings()
