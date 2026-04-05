from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

from app.common.config import get_settings
from app.dispatcher.queue import get_all_queue_lengths
from app.observability.metrics import read_counters, read_durations, recent_failure_count


_started = False


def _is_local_bind(host: str) -> bool:
    return host in {"127.0.0.1", "localhost", "::1"}


def _validate_metrics_security() -> None:
    settings = get_settings()
    app_env = getattr(settings, "app_env", "dev")
    if settings.metrics_enabled and app_env in {"prod", "production"} and not settings.metrics_token:
        raise RuntimeError("METRICS_TOKEN is required when APP_ENV is production")
    if settings.metrics_enabled and not _is_local_bind(settings.metrics_host) and not settings.metrics_token:
        raise RuntimeError(
            "METRICS_TOKEN is required when METRICS_HOST is not local-only "
            f"(current host: {settings.metrics_host})"
        )


def _is_authorized(handler: BaseHTTPRequestHandler) -> bool:
    settings = get_settings()
    expected = settings.metrics_token
    if not expected:
        return True

    auth = handler.headers.get("Authorization", "")
    if auth.startswith("Bearer ") and auth.removeprefix("Bearer ").strip() == expected:
        return True

    custom = handler.headers.get("X-Metrics-Token", "")
    return custom == expected


def _render_prometheus() -> str:
    lines: list[str] = []

    counters = read_counters()
    lines.append("# TYPE spaceforecast_counter gauge")
    for name, value in sorted(counters.items()):
        lines.append(f'spaceforecast_counter{{name="{name}"}} {value}')

    durations = read_durations()
    lines.append("# TYPE spaceforecast_duration_count gauge")
    lines.append("# TYPE spaceforecast_duration_sum_ms gauge")
    for name, (count, sum_ms) in sorted(durations.items()):
        lines.append(f'spaceforecast_duration_count{{name="{name}"}} {count}')
        lines.append(f'spaceforecast_duration_sum_ms{{name="{name}"}} {sum_ms}')

    queues = get_all_queue_lengths()
    lines.append("# TYPE spaceforecast_queue_depth gauge")
    for q, depth in sorted(queues.items()):
        lines.append(f'spaceforecast_queue_depth{{queue="{q}"}} {depth}')

    lines.append("# TYPE spaceforecast_recent_failures_5m gauge")
    for component in ("jobs", "api", "sender"):
        lines.append(
            f'spaceforecast_recent_failures_5m{{component="{component}"}} {recent_failure_count(component, minutes=5)}'
        )

    return "\n".join(lines) + "\n"


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")
            return

        if not _is_authorized(self):
            self.send_response(401)
            self.send_header("WWW-Authenticate", "Bearer")
            self.end_headers()
            self.wfile.write(b"unauthorized")
            return

        payload = _render_prometheus().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):  # noqa: A003
        return


def start_metrics_exporter() -> bool:
    global _started
    if _started:
        return False

    settings = get_settings()
    if not settings.metrics_enabled:
        return False
    _validate_metrics_security()

    server = ThreadingHTTPServer((settings.metrics_host, settings.metrics_port), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    _started = True
    return True
