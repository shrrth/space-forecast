from __future__ import annotations

import logging
from datetime import datetime
from time import perf_counter

from telegram.ext import Application, CallbackContext

from app.bot.handlers import get_handlers
from app.common.config import get_settings
from app.db.init_db import init_db
from app.dispatcher.emergency import enqueue_emergency_jobs
from app.dispatcher.refill import refill_pending_jobs_to_redis
from app.dispatcher.sender import send_pending_daily, send_pending_emergency
from app.engine.daily import enqueue_daily_jobs
from app.engine.rules import is_emergency
from app.ingestor.local_weather import fetch_and_store_local_weather
from app.ingestor.noaa import fetch_and_store_space_weather
from app.observability.alerts import check_health_and_alert, maybe_alert
from app.observability.exporter import start_metrics_exporter
from app.observability.metrics import record_job_failure, record_job_success
from app.observability.sanitize import sanitize_error_message

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def ingest_and_enqueue_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        snapshot = fetch_and_store_space_weather()
        created = 0
        if is_emergency(snapshot):
            created = enqueue_emergency_jobs(snapshot)
            logger.info("Emergency jobs enqueued=%s at=%s", created, datetime.utcnow().isoformat())
        record_job_success(
            "noaa_ingest",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=created,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("noaa_ingest", safe_error)
        logger.exception("noaa_ingest failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:noaa_ingest",
            message=f"[운영 경보] noaa_ingest 실패: {safe_error}",
        )


async def ingest_local_weather_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        created = fetch_and_store_local_weather()
        if created:
            logger.info("Local weather snapshots stored=%s at=%s", created, datetime.utcnow().isoformat())
        record_job_success(
            "local_weather_ingest",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=created,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("local_weather_ingest", safe_error)
        logger.exception("local_weather_ingest failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:local_weather_ingest",
            message=f"[운영 경보] local_weather_ingest 실패: {safe_error}",
        )


async def send_emergency_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        sent = await send_pending_emergency(context.application)
        if sent:
            logger.info("Emergency jobs sent=%s at=%s", sent, datetime.utcnow().isoformat())
        record_job_success(
            "emergency_sender",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=sent,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("emergency_sender", safe_error)
        logger.exception("emergency_sender failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:emergency_sender",
            message=f"[운영 경보] emergency_sender 실패: {safe_error}",
        )


async def enqueue_daily_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        created = enqueue_daily_jobs()
        if created:
            logger.info("Daily jobs enqueued=%s at=%s", created, datetime.utcnow().isoformat())
        record_job_success(
            "daily_enqueue",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=created,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("daily_enqueue", safe_error)
        logger.exception("daily_enqueue failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:daily_enqueue",
            message=f"[운영 경보] daily_enqueue 실패: {safe_error}",
        )


async def send_daily_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        sent = await send_pending_daily(context.application)
        if sent:
            logger.info("Daily jobs sent=%s at=%s", sent, datetime.utcnow().isoformat())
        record_job_success(
            "daily_sender",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=sent,
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("daily_sender", safe_error)
        logger.exception("daily_sender failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:daily_sender",
            message=f"[운영 경보] daily_sender 실패: {safe_error}",
        )


async def refill_queues_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        emergency = refill_pending_jobs_to_redis(job_type="emergency", limit=500)
        daily = refill_pending_jobs_to_redis(job_type="daily", limit=500)
        if emergency or daily:
            logger.info(
                "Queue refill emergency=%s daily=%s at=%s",
                emergency,
                daily,
                datetime.utcnow().isoformat(),
            )
        record_job_success(
            "queue_refill",
            duration_ms=int((perf_counter() - start) * 1000),
            processed=(emergency + daily),
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("queue_refill", safe_error)
        logger.exception("queue_refill failed")
        await maybe_alert(
            context.application,
            alert_key="job_fail:queue_refill",
            message=f"[운영 경보] queue_refill 실패: {safe_error}",
        )


async def health_monitor_job(context: CallbackContext) -> None:
    start = perf_counter()
    try:
        await check_health_and_alert(context.application)
        record_job_success(
            "health_monitor",
            duration_ms=int((perf_counter() - start) * 1000),
        )
    except Exception as exc:  # noqa: BLE001
        safe_error = sanitize_error_message(str(exc))
        record_job_failure("health_monitor", safe_error)
        logger.exception("health_monitor failed")


def run() -> None:
    settings = get_settings()
    if not settings.bot_token:
        raise RuntimeError("BOT_TOKEN is missing. Set it in .env")

    init_db()
    if start_metrics_exporter():
        logger.info(
            "Metrics exporter started at http://%s:%s/metrics",
            settings.metrics_host,
            settings.metrics_port,
        )

    app = Application.builder().token(settings.bot_token).build()
    for handler in get_handlers():
        app.add_handler(handler)

    app.job_queue.run_repeating(ingest_and_enqueue_job, interval=15 * 60, first=1, name="noaa_ingest")
    app.job_queue.run_repeating(ingest_local_weather_job, interval=60 * 60, first=5, name="local_weather_ingest")
    app.job_queue.run_repeating(send_emergency_job, interval=10, first=3, name="emergency_sender")
    app.job_queue.run_repeating(enqueue_daily_job, interval=60, first=10, name="daily_enqueue")
    app.job_queue.run_repeating(send_daily_job, interval=15, first=12, name="daily_sender")
    app.job_queue.run_repeating(refill_queues_job, interval=60, first=20, name="queue_refill")
    app.job_queue.run_repeating(health_monitor_job, interval=60, first=30, name="health_monitor")

    logger.info("Bot polling started")
    app.run_polling()


if __name__ == "__main__":
    run()
