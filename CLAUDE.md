# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Проект

Дипломный проект «Система поддержки закупочной деятельности». Две основные задачи из [Tech_doc.md](Tech_doc.md):

1. **Автозаполнение XLS-формы ЕИС** (реализована): парсинг файла «позиции» (прайс-лист) + УПД/Акт → сопоставление позиций → заполнение 7-колоночного шаблона (A–G). Три сценария: **Лидер СМИ**, **Венета** (простые), **Д-люкс** (сложный: скидка 15%, коэффициент 1.5 для «сильного загрязнения», 3 категории авто, подсветка жёлтым).
2. **Обработка реестров платежей/договоров + расчёт % СМСП** (*не реализована*, помечена в [TODO.md:3](TODO.md) как «в обсуждении»). Есть только enum-типы файлов и форма загрузки — сервисов и эндпоинтов нет.

Доп. задачи: поиск производителей по характеристикам/наименованию с экспортом, админ-панель, уведомления, dashboard.

## Запуск (полный стек)

```bash
docker-compose up -d                                                          # postgres:5433, ollama:11434
docker exec -it gazprom-ollama ollama pull mistral:7b-instruct-v0.3-q4_K_M    # один раз
cd backend && poetry install && poetry run uvicorn app.main:app --reload --port 8000
cd frontend && npm install && npm run dev                                     # http://localhost:5173
```

Дефолтный пользователь: `admin` / `admin` (создаётся автоматически в `lifespan` при старте).

## Важные особенности инфраструктуры

- **PostgreSQL мапится `5433:5432`** в [docker-compose.yml](docker-compose.yml), но [backend/app/config.py](backend/app/config.py) содержит дефолт `localhost:5432`. При локальном запуске backend вне Docker нужен `.env` с `DATABASE_URL=postgresql+asyncpg://gazprom:gazprom_secret@localhost:5433/gazprom_procurement` (аналогично для `DATABASE_URL_SYNC`).
- **Alembic настроен, но не используется**: [backend/app/main.py](backend/app/main.py) в `lifespan` вызывает `Base.metadata.create_all` — миграций нет, схема создаётся из моделей при старте. [backend/alembic.ini](backend/alembic.ini) лежит для будущего использования.
- **Разовые скрипты**: [backend/migrate_roles.py](backend/migrate_roles.py) (изменение структуры ролей), [backend/install_xlrd.py](backend/install_xlrd.py).
- **Frontend dev-proxy**: Vite проксирует `/api → http://localhost:8000` в [frontend/vite.config.js](frontend/vite.config.js).

## Архитектура — ключевые точки

### Backend ([backend/app/](backend/app/))

- **[main.py](backend/app/main.py)** — FastAPI `lifespan` создаёт таблицы, сидирует админа, подключает 6 роутеров (`auth`, `documents`, `manufacturers`, `notifications`, `admin`, `analytics`). CORS для `localhost:5173`/`3000`.
- **[api/documents.py](backend/app/api/documents.py)** — оркестрация задачи 1: `upload` → `process` (task_type=`xls_fill`, `scenario` ∈ `auto|leader_smi|veneta|d_lux`) → `download`. Задача 2 в этом роутере отсутствует.
- **[services/matcher.py](backend/app/services/matcher.py)** — гибридное сопоставление:
  - RapidFuzz: `0.45·token_set + 0.35·token_sort + 0.20·partial`, +5 за совпадение категории авто.
  - Ollama LLM (`mistral:7b-instruct-v0.3-q4_K_M`) как fallback, если fuzzy-score ∈ `[FUZZY_UNCERTAIN_THRESHOLD, FUZZY_MATCH_THRESHOLD]` = `[50, 85]` из [config.py](backend/app/config.py).
  - Для актов (Д-люкс): `_match_act_rows` применяет скидку `×0.85`, коэффициент `×1.5` при триггере `"сильн" + "загряз"`, разбивает строку на несколько услуг (`_split_act_services`), детектит категорию авто по словарю моделей.
- **[services/file_parser.py](backend/app/services/file_parser.py)** — единый вход `parse_document(path) → ParsedDocument(rows, text, metadata)`. `.xlsx` через openpyxl, `.xls` через xlrd, `.pdf` через pdfplumber. `_detect_header_row` ищет строку заголовка по keyword-score. Метаданные: `document_number` (regex по «Счет-фактура №», «Акт №»), `document_date` (`max` из всех найденных `dd.mm.yyyy`).
- **[services/xls_generator.py](backend/app/services/xls_generator.py)** — сборка финального XLS (7 колонок). Жёлтая подсветка `FFFF00` при `highlight_price` или некруглой цене. `_merge_duplicate_matches` объединяет строки по ключу `(номер позиции, цена)` с суммированием количеств.
- **[database.py](backend/app/database.py)** — async SQLAlchemy (asyncpg). Модели: [User](backend/app/models/user.py), [Document/ProcessingTask/FileType](backend/app/models/document.py), [Notification](backend/app/models/notification.py).

### Frontend ([frontend/src/](frontend/src/))

- **[App.jsx](frontend/src/App.jsx)** — React Router 6, sidebar-layout, `NotificationBell` (polling 30s), защищённые маршруты через [context/AuthContext.jsx](frontend/src/context/AuthContext.jsx) (JWT в localStorage, `authApi.me()` на mount).
- **[services/api.js](frontend/src/services/api.js)** — единый Axios-клиент с auth-interceptor, разделён на модули (`authApi`, `documentsApi`, `manufacturersApi`, `notificationsApi`, `adminApi`, `analyticsApi`).
- **Страницы** ([pages/](frontend/src/pages/)):
  - [UploadPage](frontend/src/pages/UploadPage.jsx) — dropzone, типы файлов включают `payment_registry`/`contract_registry` (но backend их не обрабатывает).
  - [ProcessingPage](frontend/src/pages/ProcessingPage.jsx) — запуск Задачи 1, явный выбор сценария.
  - [DashboardPage](frontend/src/pages/DashboardPage.jsx) — Recharts, тянет `/api/analytics/summary` + документы.
  - [ManufacturerSearchPage](frontend/src/pages/ManufacturerSearchPage.jsx) — 2 вкладки (по характеристикам / по наименованию), экспорт XLS.
  - [AdminPage](frontend/src/pages/AdminPage.jsx) — только `role=admin`, CRUD пользователей.

## Тесты

**На момент последней проверки тесты в проекте отсутствуют** (нет `backend/tests/`, нет `vitest`/`jest` в [frontend/package.json](frontend/package.json)). При добавлении тестов:

- Backend: использовать существующий `gazprom-db` из docker, заводить отдельную БД `gazprom_procurement_test` (`CREATE DATABASE` через `docker exec`). Ollama мокировать через `respx`, а не поднимать реально.
- Frontend: Vitest + @testing-library/react + msw (axios уже используется).

## Полезные команды

```bash
# Backend
poetry run uvicorn app.main:app --reload --port 8000   # запуск API
poetry run alembic revision --autogenerate -m "msg"    # (если будешь вводить миграции)

# LLM
docker logs -f gazprom-ollama                          # проверить статус Ollama
docker exec gazprom-ollama ollama list                 # список моделей

# БД
docker exec -it gazprom-db psql -U gazprom -d gazprom_procurement

# Frontend
npm run dev                                            # dev-сервер
npm run build                                          # production-сборка в dist/
```

## Соглашения

- Код и комментарии — на русском (поддержка русскоязычной документации).
- Матчинг работает по нормализованным строкам (`ё→е`, lowercase, удаление спецсимволов) — всегда нормализуй перед сравнением.
- При добавлении нового сценария обработки документа: расширить `source_file_type` в [matcher.py](backend/app/services/matcher.py), добавить ветку в `match_positions`, обновить `scenario` на фронте ([ProcessingPage.jsx](frontend/src/pages/ProcessingPage.jsx)).
- Изменения в моделях — синхронно с фронтом (типы не автогенерятся); проверь [services/api.js](frontend/src/services/api.js).
