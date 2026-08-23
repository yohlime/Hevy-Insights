from dataclasses import dataclass
from os import getenv
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv


load_dotenv()


BACKEND_DIR = Path(__file__).resolve().parents[2]


def _database_path() -> Path:
    database_path = getenv("DATABASE_PATH")
    if not database_path:
        return BACKEND_DIR / "data" / "hevy.db"

    path = Path(database_path).expanduser()
    if path.is_absolute():
        return path
    return BACKEND_DIR / path


@dataclass(frozen=True)
class Settings:
    demo_mode: bool = getenv("DEMO_MODE", "false").lower() == "true"
    sample_data_dir: Path = BACKEND_DIR / "sample_data"
    data_dir: Path = BACKEND_DIR / "data"
    log_level: str = getenv("LOG_LEVEL", "INFO")

    current_version: str = "1.8.6"
    github_repo: str = "casudo/Hevy-Insights"

    cookie_secure: bool = getenv("COOKIE_SECURE", "false").lower() == "true"
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_max_age: int = 60 * 60
    auth_session_max_age: int = 60 * 60 * 24 * 365
    database_path: Path = _database_path()
    database_url: str = f"sqlite:///{database_path}"

    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://localhost:80",
    )


settings = Settings()
