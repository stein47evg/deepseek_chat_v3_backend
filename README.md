DeepSeek Chat Backend

Бэкенд для AI-ассистента разработчика с управлением файловой системой

## Установка

1. Создать виртуальное окружение:
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   venv\Scripts\activate     # Windows

2. Установить зависимости:
   pip install -r requirements.txt

3. Создать файл .env (скопировать из .env.example):
   cp .env.example .env
   # Заполнить DEEPSEEK_API_KEY и DATABASE_URL

4. Инициализировать базу данных:
   python scripts/init_db.py
   python scripts/seed_prompts.py

5. Запустить сервер:
   python main.py
   # или
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload

## API Документация

После запуска доступны:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Основные эндпоинты

- POST /api/v1/chats/{chat_id}/generate - генерация кода (SSE стрим)
- POST /api/v1/projects - создание проекта
- POST /api/v1/projects/{project_id}/sync - синхронизация
- GET /api/v1/projects/{project_id}/snapshots - история состояний

## Структура проекта

.
├── main.py                # Точка входа
├── app/
│   ├── core/              # Конфигурация, БД, исключения
│   ├── models/            # SQLAlchemy модели
│   ├── schemas/           # Pydantic схемы
│   ├── services/          # Бизнес-логика
│   ├── api/v1/            # Эндпоинты
│   └── utils/             # Утилиты
├── scripts/               # Вспомогательные скрипты
├── requirements.txt
└── .env.example
