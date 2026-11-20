# ПотребКонсульт

Учебный ассистент по защите прав потребителей. Поиск использует BGE-M3 и PostgreSQL 16 с pgvector. Qwen получает вопрос и выдержки из базы. В карточке консультации можно прочесть источники, скопировать шаблон претензии и оценить ответ.

## Быстрый показ ДЗ 4

В PowerShell из корня проекта:

```powershell
cd frontend
npm ci
npm run dev
```

Откройте http://localhost:5173/demo. Раскройте статью, поставьте оценку и откройте черновик. На узком экране источники располагаются ниже ответа. Демонстрация работает автономно. [Отчёт](hw4/development_report.md).

## Локальный стенд ДЗ 5

Нужны Docker Desktop с Linux-контейнерами, Python 3.11+, Node.js 22 и Ollama. PostgreSQL хранит данные в томе pgdata. Из корня проекта выполните:

```powershell
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Для новой установки задайте свой пароль в POSTGRES_PASSWORD и DATABASE_URL в .env. Если том уже существует, используйте пароль существующей базы. Следующие команды предполагают имена БД и пользователя из .env.example.

```powershell
docker compose up -d --wait db
docker compose exec db psql -U potreb -d potrebkonsult -v ON_ERROR_STOP=1 -f /migrations/001_create_documents_and_chunks.sql -f /migrations/002_consultations.sql
ollama pull bge-m3
ollama pull qwen2.5:7b
cd backend
if (!(Test-Path .venv)) { py -3.11 -m venv .venv }
.\.venv\Scripts\python -m pip install -e ".[dev]"
```

При первом запуске заполните базу из каталога backend, затем запустите API:

```powershell
.\.venv\Scripts\python -m app.rag.indexer --file ../data/zozpp_2025-12-28.txt --key zozpp --title "Закон РФ «О защите прав потребителей»" --edition-date 2025-12-28
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

Запустите frontend в другом терминале по инструкции ДЗ 4. Откройте http://localhost:5173/, создайте аккаунт, задайте вопрос длиной от 10 до 2000 символов. После обновления страницы консультация останется в истории. [Архитектура, API и примеры](hw5/backend_documentation.md).

## Проверка

Из frontend выполните `npm test` и `npm run build`. Для интеграционных тестов нужна отдельная БД с именем, заканчивающимся на `_test`. Тесты очищают документы в этой БД. При первом запуске из корня:

```powershell
docker compose exec db createdb -U potreb potrebkonsult_test
docker compose exec db psql -U potreb -d potrebkonsult_test -v ON_ERROR_STOP=1 -f /migrations/001_create_documents_and_chunks.sql -f /migrations/002_consultations.sql
cd backend
.\.venv\Scripts\python -m pytest -q
.\.venv\Scripts\ruff check .
.\.venv\Scripts\python -m mypy --strict app tests
```

Укажите TEST_DATABASE_URL в .env для тестовой БД. Пользовательские тексты и пароли в отчёты не включайте.
