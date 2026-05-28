import os
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, PostgresDsn

class Settings(BaseSettings):
    PROJECT_NAME: str = "Page-to-API Platform"
    API_V1_STR: str = "/v1"
    
    # Database
    DATABASE_URL: str = Field(
        default="postgresql://postgres:password123@localhost:5432/pagetoapi",
        validation_alias="DATABASE_URL"
    )
    
    # Redis
    REDIS_URL: str = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL"
    )
    
    # Security
    API_KEY_HEADER: str = "X-API-KEY"
    JWT_SECRET_KEY: str = Field(
        default="9a8d7c6b5a4d3c2b1a0f9e8d7c6b5a4d3c2b1a0f9e8d7c6b5a4d3c2b1a0f9e8d",
        validation_alias="JWT_SECRET_KEY"
    )
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    
    # AI Provider Settings
    AI_PROVIDER: str = "openai"  # openai, anthropic, openai_compatible
    
    # OpenAI Settings
    OPENAI_API_KEY: Optional[str] = Field(default=None, validation_alias="OPENAI_API_KEY")
    OPENAI_API_BASE_URL: Optional[str] = Field(default=None, validation_alias="OPENAI_API_BASE_URL")
    OPENAI_VISION_MODEL: str = "gpt-4o"
    OPENAI_CODEGEN_MODEL: str = "gpt-4o"
    
    # Anthropic Settings
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    ANTHROPIC_MODEL: str = "claude-3-5-sonnet-20241022"
    
    # Crawler Settings
    PLAYWRIGHT_HEADLESS: bool = True
    PLAYWRIGHT_TIMEOUT_MS: int = 30000
    
    # Proxy Settings
    PROXY_SERVER: Optional[str] = Field(default=None, validation_alias="PROXY_SERVER")
    PROXY_USERNAME: Optional[str] = Field(default=None, validation_alias="PROXY_USERNAME")
    PROXY_PASSWORD: Optional[str] = Field(default=None, validation_alias="PROXY_PASSWORD")

    # Sandbox Settings
    SANDBOX_TIMEOUT_SEC: float = 5.0
    SANDBOX_MEMORY_LIMIT_MB: int = 256
    
    # Razorpay Settings
    RAZORPAY_KEY_ID: Optional[str] = Field(default=None, validation_alias="RAZORPAY_KEY_ID")
    RAZORPAY_KEY_SECRET: Optional[str] = Field(default=None, validation_alias="RAZORPAY_KEY_SECRET")
    
    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:8000"]
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

settings = Settings()
