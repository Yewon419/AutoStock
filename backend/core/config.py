from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql://autostock:autostock123@localhost:5432/autostock"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # JWT
    JWT_SECRET_KEY: str = "dev-secret-key"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24

    # Encryption
    ENCRYPTION_KEY: str = ""

    # Broker
    BROKER_MODE: str = "mock"  # mock | paper | real

    # KIS (한국투자증권)
    KIS_APP_KEY: str = ""
    KIS_APP_SECRET: str = ""
    KIS_ACCOUNT_NO: str = ""      # 예: 12345678-01
    KIS_IS_PAPER: bool = True     # True=모의투자, False=실계좌

    # Anthropic (Claude API)
    ANTHROPIC_API_KEY: str = ""

    # DART 전자공시 (2단계용)
    DART_API_KEY: str = ""

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",")]

    class Config:
        env_file = ".env"


settings = Settings()
