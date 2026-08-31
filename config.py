from dataclasses import dataclass
import os


def ints(name: str) -> set[int]:
    return {int(x.strip()) for x in os.getenv(name, "").split(",") if x.strip()}

@dataclass(frozen=True)
class Settings:
    bot_token: str = os.getenv("BOT_TOKEN", "")
    database_url: str = os.getenv("DATABASE_URL", "")
    source_chat_id: int = int(os.getenv("SOURCE_CHAT_ID", "0"))
    global_thread_id: int = int(os.getenv("GLOBAL_THREAD_ID", "0"))
    operational_thread_id: int = int(os.getenv("OPERATIONAL_THREAD_ID", "0"))
    monthly_thread_id: int = int(os.getenv("MONTHLY_THREAD_ID", "0"))
    allowed_user_ids: set[int] = None
    admin_user_id: int = int(os.getenv("ADMIN_USER_ID", "0"))
    timezone: str = os.getenv("TZ", "Europe/Nicosia")
    log_level: str = os.getenv("LOG_LEVEL", "INFO")

    def __post_init__(self):
        object.__setattr__(self, "allowed_user_ids", ints("ALLOWED_USER_IDS"))

settings = Settings()
