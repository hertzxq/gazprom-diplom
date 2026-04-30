# Система поддержки закупочной деятельности

Веб-система для автоматизации закупочных процессов: автозаполнение XLS-форм для ЕИС, обработка реестров, поиск производителей.

## Стек технологий

| Компонент | Технология |
|-----------|-----------|
| Frontend | React 18 + Vite |
| Backend | FastAPI (Python) |
| БД | PostgreSQL 16 (Docker) |
| LLM | Ollama + Mistral 7B Q4 |
| OCR | Tesseract + OpenCV |

## Быстрый старт

### Предварительные требования

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) — для PostgreSQL и Ollama
- [Python 3.11+](https://www.python.org/downloads/)
- [Node.js 20+](https://nodejs.org/)

### 1. Запуск базы данных и LLM

```bash
docker-compose up -d
```

Дождитесь запуска PostgreSQL, затем загрузите модель LLM:

```bash
docker exec -it gazprom-ollama ollama pull mistral:7b-instruct-v0.3-q4_K_M
```

### 2. Запуск бэкенда

```bash
cd backend
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

API будет доступен по адресу: http://localhost:8000/docs

### 3. Запуск фронтенда

```bash
cd frontend
npm install
npm run dev
```

Приложение откроется по адресу: http://localhost:5173

### 4. Вход в систему

Стандартные учётные данные:
- **Логин:** `admin`
- **Пароль:** `admin`

## Структура проекта

```
gazprom-diplom/
├── docker-compose.yml       # PostgreSQL + Ollama
├── backend/
│   ├── app/
│   │   ├── main.py          # FastAPI entrypoint
│   │   ├── config.py        # Настройки
│   │   ├── database.py      # SQLAlchemy async
│   │   ├── models/          # User, Document, ProcessingTask
│   │   ├── api/             # auth, documents
│   │   ├── services/        # file_parser, matcher, xls_generator, ocr
│   │   ├── schemas/         # Pydantic-схемы
│   │   └── utils/           # auth utilities
│   └── requirements.txt
└── frontend/
    ├── src/
    │   ├── App.jsx           # Routing + sidebar
    │   ├── pages/            # Login, Dashboard, Upload, Processing
    │   ├── services/         # API client
    │   └── context/          # Auth context
    └── package.json
```
