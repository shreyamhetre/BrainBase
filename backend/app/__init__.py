# Load .env before any library is imported: huggingface_hub reads HF_HUB_OFFLINE at import time.
from app import config  # noqa: F401
