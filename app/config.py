"""Application configuration.

All settings come from environment variables (with sensible defaults) so the
same code runs locally, in Docker, and in tests. This keeps configuration in
one place and makes the app easy to deploy.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --- Database ---
    # PostgreSQL with the pgvector extension. docker-compose provides this URL;
    # for a non-Docker run, point DATABASE_URL at your own Postgres instance.
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/ragdb"

    # --- Auth / JWT ---
    jwt_secret: str = "change-me-in-prod"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 60

    # --- Embeddings ---
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dim: int = 384  # dimension of all-MiniLM-L6-v2

    # --- LLM: Groq (hosted, free tier) ---
    # The API key is read from the GROQ_API_KEY env var. Leave empty to disable.
    groq_api_key: str = ""
    groq_model: str = "openai/gpt-oss-20b"
    groq_url: str = "https://api.groq.com/openai/v1/chat/completions"

    # --- LLM: Ollama (optional, local & free) ---
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"

    # --- RAG parameters ---
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 4

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
