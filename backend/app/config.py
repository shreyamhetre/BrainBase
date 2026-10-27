"""Settings loaded from the project-root .env file."""

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

DATABASE_URL = os.environ["DATABASE_URL"]
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.openai.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")  # GPT-4o mini
# US dollars per million tokens, for the usage log (GPT-4o mini list prices; change with the model)
LLM_PRICE_INPUT_PER_M = float(os.getenv("LLM_PRICE_INPUT_PER_M", "0.15"))
LLM_PRICE_OUTPUT_PER_M = float(os.getenv("LLM_PRICE_OUTPUT_PER_M", "0.60"))
TYPESAFE_API_KEY = os.getenv("TYPESAFE_API_KEY", "")  # Jev evidence gate; empty = gate skipped

JWT_SECRET = os.getenv("JWT_SECRET", "")
JWT_EXPIRE_HOURS = int(os.getenv("JWT_EXPIRE_HOURS", "24"))
ALLOWED_EMAIL_DOMAIN = os.getenv("ALLOWED_EMAIL_DOMAIN", "gitmore.com").lower()  # company accounts only

SECRETS_KEY = os.getenv("SECRETS_KEY", "")  # encrypts connector and MCP tokens in the database
SYNC_SCHEDULER = os.getenv("SYNC_SCHEDULER", "1") != "0"  # background connector sync in the API

DATA_DIR = PROJECT_ROOT / "data"
MIGRATIONS_DIR = PROJECT_ROOT / "db" / "migrations"

EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_DIM = 1024
RERANK_MODEL = "BAAI/bge-reranker-v2-m3"
