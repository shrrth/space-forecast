from __future__ import annotations

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    app_env: str
    bot_token: str
    database_url: str
    redis_url: str
    default_timezone: str
    default_location_label: str
    default_lat: float
    default_lon: float
    noaa_kp_api: str
    noaa_xray_api: str
    openweather_api_url: str
    openweather_api_key: str
    openmeteo_api_url: str
    kma_api_url: str
    kma_service_key: str
    alert_chat_id: str
    alert_webhook_url: str
    alert_queue_threshold: int
    alert_failure_threshold: int
    alert_cooldown_sec: int
    sender_max_retries: int
    sender_retry_base_sec: int
    sender_retry_max_sec: int
    metrics_enabled: bool
    metrics_host: str
    metrics_port: int
    metrics_token: str
    ops_admin_ids: str


def get_settings() -> Settings:
    return Settings(
        app_env=os.getenv("APP_ENV", "dev").strip().lower(),
        bot_token=os.getenv("BOT_TOKEN", ""),
        database_url=os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://spaceforecast:spaceforecast@localhost:5432/spaceforecast",
        ),
        redis_url=os.getenv("REDIS_URL", "redis://localhost:6379/0"),
        default_timezone=os.getenv("DEFAULT_TIMEZONE", "Asia/Seoul"),
        default_location_label=os.getenv("DEFAULT_LOCATION_LABEL", "Seoul"),
        default_lat=float(os.getenv("DEFAULT_LAT", "37.5665")),
        default_lon=float(os.getenv("DEFAULT_LON", "126.9780")),
        noaa_kp_api=os.getenv(
            "NOAA_KP_API",
            "https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json",
        ),
        noaa_xray_api=os.getenv(
            "NOAA_XRAY_API",
            "https://services.swpc.noaa.gov/json/goes/primary/xrays-1-day.json",
        ),
        openweather_api_url=os.getenv(
            "OPENWEATHER_API_URL",
            "https://api.openweathermap.org/data/2.5/weather",
        ),
        openweather_api_key=os.getenv("OPENWEATHER_API_KEY", ""),
        openmeteo_api_url=os.getenv(
            "OPENMETEO_API_URL",
            "https://api.open-meteo.com/v1/forecast",
        ),
        kma_api_url=os.getenv(
            "KMA_API_URL",
            "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst",
        ),
        kma_service_key=os.getenv("KMA_SERVICE_KEY", ""),
        alert_chat_id=os.getenv("ALERT_CHAT_ID", ""),
        alert_webhook_url=os.getenv("ALERT_WEBHOOK_URL", ""),
        alert_queue_threshold=int(os.getenv("ALERT_QUEUE_THRESHOLD", "500")),
        alert_failure_threshold=int(os.getenv("ALERT_FAILURE_THRESHOLD", "20")),
        alert_cooldown_sec=int(os.getenv("ALERT_COOLDOWN_SEC", "300")),
        sender_max_retries=int(os.getenv("SENDER_MAX_RETRIES", "5")),
        sender_retry_base_sec=int(os.getenv("SENDER_RETRY_BASE_SEC", "30")),
        sender_retry_max_sec=int(os.getenv("SENDER_RETRY_MAX_SEC", "1800")),
        metrics_enabled=os.getenv("METRICS_ENABLED", "true").lower() in {"1", "true", "yes", "on"},
        metrics_host=os.getenv("METRICS_HOST", "127.0.0.1"),
        metrics_port=int(os.getenv("METRICS_PORT", "9108")),
        metrics_token=os.getenv("METRICS_TOKEN", ""),
        ops_admin_ids=os.getenv("OPS_ADMIN_IDS", ""),
    )
