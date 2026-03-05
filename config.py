import os
from dotenv import load_dotenv

load_dotenv()

# Jina Reader API Configuration
JINA_BASE_URL: str = os.environ.get("JINA_BASE_URL", "https://r.jina.ai/")

# Fetcher Configuration
FETCH_TIMEOUT: int = int(os.environ.get("FETCH_TIMEOUT", "15"))
FETCH_MAX_RETRIES: int = int(os.environ.get("FETCH_MAX_RETRIES", "2"))
USER_AGENT: str = os.environ.get("USER_AGENT", "SugarProtocol/0.1")

# LLM Configuration
OPENAI_API_KEY: str = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_MODEL: str = os.environ.get("DEFAULT_MODEL", "gpt-4o-mini")
LLM_MAX_RETRIES: int = int(os.environ.get("LLM_MAX_RETRIES", "3"))
LLM_TIMEOUT: int = int(os.environ.get("LLM_TIMEOUT", "30"))

# Thresholds
MIN_CONTENT_LENGTH: int = 10

# Database Configuration
DB_URL: str = os.environ.get("DB_URL", "sqlite+aiosqlite:///sugar.db")
FUZZY_MATCH_THRESHOLD: int = int(os.environ.get("FUZZY_MATCH_THRESHOLD", "85"))
ENTITY_SEED_PATH: str = os.environ.get("ENTITY_SEED_PATH", "pipeline/entity_seed.json")
