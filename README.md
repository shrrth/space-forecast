# Space Forecast

## Quick start

1. Create env file:
```bash
cp .env.example .env
```

2. Start infrastructure:
```bash
docker compose up -d
```

3. Install dependencies:
```bash
/opt/homebrew/bin/python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

4. Run app:
```bash
python -m app.main
```

## Current scope

- Telegram commands: `/start`, `/setlocation`, `/setequipment`, `/setpurpose`, `/setlang`, `/status`, `/opsstatus`(admin), `/help`
- Location save with timezone resolution
- NOAA 15-minute ingest scheduler
- Local weather ingest scheduler (OpenWeather -> KMA(for KR) -> Open-Meteo, 1 hour)
  - weather fields: cloud/humidity/temp/wind + precipitation probability/amount
- Emergency rule: `Kp >= 6` or `X-class`
- Emergency queue + 3-hour cooldown per user (Redis queue)
- Daily report queue (user local 18:00 default, Redis queue)
- Throttled sender (max ~30 msg/sec)
- Retry policy for sender (exponential backoff + max retries)
- Queue refill job for due pending DB messages (1 min)
- Ops metrics (job/api success-failure, duration, failure buckets)
- Ops alerts (queue backlog/failure spike with cooldown)
- DB tables and migration SQL (`migrations/001_init.sql`, `migrations/002_message_job_retry.sql`, `migrations/003_local_weather_temp_wind.sql`, `migrations/004_user_profile_params.sql`, `migrations/005_local_weather_precip.sql`, `migrations/006_user_language_code.sql`)

## Required env

- `BOT_TOKEN`
- `OPENWEATHER_API_KEY` (optional)
- `KMA_SERVICE_KEY` (optional, used for Korea fallback)
- `ALERT_CHAT_ID` (optional, Telegram chat id for ops alerts)
- `ALERT_WEBHOOK_URL` (optional, Slack/Webhook endpoint)
- `ALERT_QUEUE_THRESHOLD`, `ALERT_FAILURE_THRESHOLD`, `ALERT_COOLDOWN_SEC`
- `SENDER_MAX_RETRIES`, `SENDER_RETRY_BASE_SEC`, `SENDER_RETRY_MAX_SEC`
- `METRICS_ENABLED`, `METRICS_HOST`, `METRICS_PORT`, `METRICS_TOKEN`
- `OPS_ADMIN_IDS` (comma-separated Telegram user ids)
- Personalization values
  - `/setequipment <visual|basic|advanced>`
  - `/setpurpose <deep_sky|planetary|widefield>`
  - `/setlang <ko|en>`

## Metrics endpoint

- Prometheus format endpoint: `GET /metrics`
- Default bind: `127.0.0.1:9108`
- Optional auth: `Authorization: Bearer <METRICS_TOKEN>` or `X-Metrics-Token: <METRICS_TOKEN>`
- Security enforcement:
  - `METRICS_HOST` non-local (`0.0.0.0` etc.) + token empty -> startup fail
  - `APP_ENV=prod|production` + token empty -> startup fail

## Prometheus/Grafana

1. Start app metrics endpoint (local):
```bash
METRICS_ENABLED=true METRICS_HOST=0.0.0.0 METRICS_PORT=9108 METRICS_TOKEN=secret python -m app.main
```

2. Start observability stack:
```bash
docker compose up -d prometheus grafana
```

3. Open:
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000` (`admin` / `admin`)

Provisioned resources:
- Prometheus scrape config: `observability/prometheus/prometheus.yml`
- Grafana datasource: `observability/grafana/provisioning/datasources/prometheus.yml`
- Grafana dashboard: `observability/grafana/dashboards/spaceforecast-overview.json`

Notes:
- Prometheus target is `host.docker.internal:9108` (Docker Desktop/macOS 기준).
- Linux에서는 `host.docker.internal` 해석이 안 되면 `observability/prometheus/prometheus.yml` 타깃을 호스트 IP로 바꿔야 합니다.

## Ops preflight

Run before deploy/start:

```bash
python -m app.common.preflight
```

- returns `preflight: ok` on pass
- exits with error when metrics access policy is violated

## Tests

```bash
python -m pytest -q
python -m pytest -q tests/e2e
```

## CI

- GitHub Actions workflow: `.github/workflows/ci.yml`
- Trigger: push (`main`/`master`), pull request
- Steps: `pip install -e ".[dev]"` -> `ruff check` -> `pytest`

## Deployment automation

- Staging workflow: `.github/workflows/deploy-staging.yml`
  - Trigger: push (`main`/`master`) or manual dispatch
  - Flow: Docker image build/push (GHCR) -> remote compose deploy
- Production workflow: `.github/workflows/deploy-prod.yml`
  - Trigger: manual dispatch
  - Flow: Docker image build/push (GHCR) -> remote compose deploy

Deployment assets:
- `Dockerfile`
- `deploy/docker-compose.staging.yml`
- `deploy/docker-compose.prod.yml`

Required GitHub secrets:
- Shared: `GHCR_READ_USER`, `GHCR_READ_TOKEN`
- Staging: `STAGING_HOST`, `STAGING_USER`, `STAGING_SSH_KEY`, `STAGING_PORT`, `STAGING_DEPLOY_PATH`, `STAGING_ENV_FILE`
- Production: `PROD_HOST`, `PROD_USER`, `PROD_SSH_KEY`, `PROD_PORT`, `PROD_DEPLOY_PATH`, `PROD_ENV_FILE`
