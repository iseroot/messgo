# messgo

Лёгкий приватный мессенджер MVP на FastAPI с invite-only регистрацией, чатами, статусами сообщений, сигналингом звонков и минималистичным PWA UI.

## Стек

- Python 3.12+
- FastAPI + Uvicorn
- SQLAlchemy 2.0 + SQLite
- Jinja2 + HTMX + vanilla JS
- Caddy (HTTPS/HTTP2 и статика)
- coturn (TURN/STUN для WebRTC)

## Структура (чистая архитектура)

- `app/domain` — доменные enum/правила.
- `app/application` — use-case сервисы и ошибки.
- `app/infrastructure` — БД и SQLAlchemy-репозитории.
- `app/presentation` — API, страницы, WebSocket.
- `tests/unit`, `tests/integration`, `tests/e2e` — тестовая пирамида.

## Быстрый старт локально

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
cp .env.example .env
uvicorn app.main:app --reload
```

Сервис поднимется на `http://127.0.0.1:8000`.

## Проверки качества

```bash
ruff check .
pytest -q
python tools/run_mutation_tests.py --fail-on-survivor
```

## Деплой

- Конфиг Caddy: `deploy/Caddyfile`
- systemd unit: `deploy/systemd/messgo.service`
- Скрипт деплоя: `deploy/scripts/deploy.sh`
- Пример TURN-конфига: `deploy/turnserver.conf.example`

Локальный запуск деплоя на сервере:

```bash
bash deploy/scripts/deploy.sh main
```

## GitHub Actions

- `CI`: lint + unit/integration/e2e + покрытие + мутационные тесты.
- `Deploy`: автодеплой после успешного `CI` на `main`.

Список нужных secrets: `.github/SECRETS.md`.
