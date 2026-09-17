# AGENTS.md — LabManager

## What this is

FastAPI + TimescaleDB + MQTT lab sensor monitoring app. Server-rendered Jinja2 templates, vanilla JS, no build step. All UI in Spanish (Argentina, default timezone `Etc/GMT+3` = UTC-3).

## Run

```bash
# Docker (recommended)
docker compose up --build          # app on :8082, db on :5432, mqtt on :1883

# Local dev (needs running db + mqtt)
source .venv/bin/activate
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Dev override (`docker-compose.override.yml`) mounts `./app` into the container and runs with `--reload`. Code changes are live without rebuild.

## Test / Lint / Typecheck

None configured. No tests, no linting, no typecheck. Validate changes manually against running containers.

## Architecture

```
app/main.py              → FastAPI entrypoint, lifespan (init_db, seed_admin, start_mqtt), dashboard /
app/config.py            → env var loading
app/database.py          → SQLAlchemy engine + custom migrations (no Alembic) + TimescaleDB hypertable
app/models.py            → 7 ORM tables: users, units, sensors, experiments, experiment_sensors, sensor_data, notes, note_images
app/mqtt.py              → MQTT ingestor (paho-mqtt, daemon thread), parses payload → sensor_data rows
app/realtime.py          → WebSocket /ws/data live push
app/auth.py              → bcrypt + itsdangerous session tokens
app/templating.py        → Jinja2 setup + filters: dth, dtlocal, usym
app/routers/             → route modules (auth, users, experiments, sensors, units, data, notes)
app/templates/           → Jinja2 HTML (extends base.html, except login.html)
app/static/              → Bootstrap 5, Chart.js, custom CSS/JS (all bundled offline, no CDN)
scripts/sim_sensor.py    → MQTT sensor simulator CLI
```

## Key facts for editing

- **Unit display**: always show the unit SYMBOL in parentheses after sensor names (e.g. `temperature (°C)`). If no symbol exists, show the unit NAME. Never show both name and symbol. The `usym` Jinja2 filter (`templating.py`) handles this: returns `unit.symbol if unit.symbol else unit.name`. Use it everywhere units are displayed. Backend fields (`main.py`, `data_routes.py`) must also fallback: `symbol or name`.
- **Timezone**: all timestamps are UTC in the DB. UI displays in the configured fixed UTC offset (`Etc/GMT+N`, default `Etc/GMT+3` = UTC-3, no DST) via `dth`/`dtlocal` filters and JS `fmtTime()`.
- **Roles**: `admin`, `investigador`, `lector` (read-only). Enforced via `require_roles()` in `web.py`.
- **Sensor→Experiment association**: `experiment_sensors` join table. Sensor data is NOT scoped to experiments — it's global by `sensor_id` + `time`.
- **Data query**: `/api/data` and `/api/data/csv` accept `from` (ISO datetime), `to`, `sensor_id`, `experiment_id`, `limit`. Period defaults: no filter → 24h, explicit `from=""` (Todo) → no time limit. Uniform sampling when points > limit.
- **MQTT ingest**: payload must be parseable as float or bool (`true/1/on/yes`). Unparseable messages are silently ignored. Sensor matched by `mqtt_topic` exact match + `is_active`.
- **Custom migration**: `database.py:_migrate_schema()` does in-place ALTERs — no Alembic. Be careful adding new migrations here.

## Gotchas

- `.env` is committed in dev with default credentials (`admin`/`admin123`). Production needs all secrets changed.
- Mosquitto runs `allow_anonymous true` — lab only.
- No test suite exists. Test manually against running Docker stack using `curl` or browser.
- Database session management: each request gets its own session via `get_db()` generator. Never hold sessions across requests.
- Frontend JS is vanilla — no npm, no bundler, no framework. Edit `app/static/js/app.js` directly.
