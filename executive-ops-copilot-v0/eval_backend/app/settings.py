from os import getenv


class Settings:
    def __init__(self) -> None:
        self.ai_backend_url = getenv("AI_BACKEND_URL", "http://localhost:9000").rstrip("/")
        self.eval_db_path = getenv("EVAL_DB_PATH", "./data/evals.db")
        self.request_timeout_seconds = float(getenv("EVAL_REQUEST_TIMEOUT_SECONDS", "180"))


def get_settings() -> Settings:
    return Settings()
