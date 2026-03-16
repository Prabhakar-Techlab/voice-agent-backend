from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # MongoDB
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "stt_conversations"

    # Default STT provider (sarvam | groq)
    stt_provider: str = "sarvam"

    # Sarvam AI
    sarvam_api_key: str | None = None

    # Groq (Whisper)
    groq_api_key: str | None = None

    # Deepgram (Nova-2)
    deepgram_api_key: str | None = None

    # AssemblyAI
    assemblyai_api_key: str | None = None

    # Anthropic Claude API
    anthropic_api_key: str | None = None


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
