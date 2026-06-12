from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    # Database. Дефолт — порт 5433: на него маппится контейнер gazprom-db
    # из docker-compose.yml (5433:5432), чтобы не конфликтовать с локальным PostgreSQL.
    DATABASE_URL: str = "postgresql+asyncpg://gazprom:gazprom_secret@localhost:5433/gazprom_procurement"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://gazprom:gazprom_secret@localhost:5433/gazprom_procurement"

    # Ollama LLM
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral:7b-instruct-v0.3-q4_K_M"
    # Для поиска производителей по умолчанию используем компактную qwen2.5:1.5b —
    # она помещается в стандартный лимит памяти Docker Desktop / WSL2 (~3 GiB).
    # Если выделить Docker'у больше RAM, рекомендуется переключиться на mistral:7b
    # через .env: OLLAMA_SEARCH_MODEL=mistral:7b-instruct-v0.3-q4_K_M
    OLLAMA_SEARCH_MODEL: str = "qwen2.5:1.5b"

    # File storage. Абсолютные пути от корня backend/ — иначе при запуске uvicorn
    # из другого каталога файлы пишутся в CWD и скачивание отдаёт 404.
    UPLOAD_DIR: Path = Path(__file__).resolve().parent.parent / "uploads"
    GENERATED_DIR: Path = Path(__file__).resolve().parent.parent / "generated"
    TEMPLATES_DIR: Path = Path(__file__).resolve().parent.parent / "templates"

    # JWT Auth
    SECRET_KEY: str = "change-me-in-production-gazprom-secret-key-2024"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480  # 8 hours

    # OCR
    TESSERACT_CMD: str = "tesseract"
    OCR_CONFIDENCE_THRESHOLD: float = 0.7

    # Matcher
    FUZZY_MATCH_THRESHOLD: float = 85.0
    FUZZY_UNCERTAIN_THRESHOLD: float = 50.0
    # LLM-верификация спорных позиций (зона [50, 85)). На CPU генерация Mistral 7B
    # занимает ~47 с при таймауте 20 с — каждый вызов лишь замедляет обработку,
    # поэтому с фронта флаг передаётся явно (по умолчанию выключен в UI).
    LLM_MATCHER_ENABLED: bool = True
    LLM_TIMEOUT_SECONDS: float = 20.0

    class Config:
        # Абсолютный путь: .env должен находиться рядом с каталогом app/,
        # независимо от того, из какого каталога запущен uvicorn.
        env_file = str(Path(__file__).resolve().parent.parent / ".env")
        case_sensitive = True


settings = Settings()


# Дефолтный перечень правил категоризации «Исключение из СМСП».
# Используется при первом старте приложения: если таблица smsp_exclusion_rules
# пуста — сюда сидируются эти строки. Потом админ правит их через API.
# Формат: (category, keywords, point_letter, order_idx).
SMSP_DEFAULT_RULES: list[tuple[str, list[str], str | None, int]] = [
    ("авиа",    ["воздушн", "авиац", "авиа"],                           "р",  10),
    ("страх",   ["страхов", "финансов", "банковск", "лизинг"],          "д",  20),
    ("образов", ["образоват", "обучен"],                                "ц",  30),
    ("аренда",  ["аренд", "недвижим"],                                  "л",  40),
    ("почта",   ["почтов", "связ"],                                     None, 50),
]
