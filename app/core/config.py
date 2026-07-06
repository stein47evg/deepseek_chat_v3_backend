import os
from typing import List
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # База данных
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "3306")
    DB_USER: str = os.getenv("DB_USER", "root")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    DB_NAME: str = os.getenv("DB_NAME", "deepseek_dev")

    @property
    def DATABASE_URL(self) -> str:
        """Собирает URL для подключения к БД."""
        return f"mysql+pymysql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    # API DeepSeek
    DEEPSEEK_API_KEY: str = os.getenv("DEEPSEEK_API_KEY", "")
    DEEPSEEK_BASE_URL: str = "https://api.deepseek.com"
    DEEPSEEK_MODEL_FLASH: str = "deepseek-chat"
    DEEPSEEK_MODEL_PRO: str = "deepseek-reasoner"

    # Окружение
    ENV: str = os.getenv("ENV", "development")
    DEBUG: bool = ENV == "development"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Ограничения файлов
    MAX_FILE_SIZE: int = 10 * 1024 * 1024
    ALLOWED_EXTENSIONS: set = {
        ".py", ".js", ".ts", ".jsx", ".tsx",
        ".html", ".htm", ".css", ".scss", ".sass", ".less",
        ".json", ".yaml", ".yml", ".toml",
        ".md", ".mdx",
        ".sh", ".bash", ".zsh",
        ".c", ".h", ".cpp", ".hpp", ".cc", ".cxx",
        ".rs", ".go", ".java", ".kt", ".kts",
        ".php", ".rb", ".swift",
        ".sql", ".xml", ".svg",
        ".graphql", ".gql",
        ".vue", ".svelte",
        ".txt", ".log", ".csv", ".tsv",
        ".ini", ".cfg", ".conf",
        "Dockerfile", ".dockerignore",
        ".gitignore", ".gitattributes",
        ".env"
    }

    # Параметры модели
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_REASONING: bool = True
    DEFAULT_MODEL: str = "flash"

    # Лимиты контекста
    MAX_CONTEXT_TOKENS: int = 800_000
    HISTORY_LIMIT: int = 10


settings = Settings()
