import os

DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"


def openai_responses_url() -> str:
    base_url = os.getenv("OPENAI_BASE_URL", DEFAULT_OPENAI_BASE_URL).strip()
    if not base_url:
        base_url = DEFAULT_OPENAI_BASE_URL
    return f"{base_url.rstrip('/')}/responses"
