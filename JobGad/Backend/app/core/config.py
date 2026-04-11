from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List
from typing import ClassVar

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Powered Graduate Career Acceleration Platform"
    PROJECT_VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Environment (development, testing, production)
    ENVIRONMENT: str = "development"

    # CORS settings
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000"]
    
    # Database Settings
    DB_USER: str = "career_user"
    DB_PASSWORD: str = "strong_password_here"
    DB_HOST: str = "localhost"
    DB_PORT: str = "5432"
    DB_NAME: str = "career_platform"
    
    # JWT Security Settings
    SECRET_KEY: str = "your_256_bit_secret_key_here"  # Default placeholder for local dev
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AI APIs
    GEMINI_API_KEY: str = ""
    
    # Pinecone
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
    
    # MinIO
    MINIO_USER: str = "minioadmin"
    MINIO_PASSWORD: str = "minioadmin"
    MINIO_ENDPOINT: str = "localhost:9000"

    DATABASE_URL: str | None = None

    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env", 
        env_file_encoding="utf-8", 
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def DATABASE_URI(self) -> str:
        if self.DATABASE_URL:
            # SQLAlchemy asyncpg requires postgresql+asyncpg schema
            if self.DATABASE_URL.startswith("postgresql://"):
                return self.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://", 1)
            return self.DATABASE_URL
        return f"postgresql+asyncpg://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

settings = Settings()
