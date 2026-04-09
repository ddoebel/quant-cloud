from celery import Celery
import os
from urllib.parse import urlparse

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "quant")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "changeme")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST") or os.getenv("RABBITMQ_SERVICE_HOST") or "rabbitmq.quant-cloud.svc.cluster.local"
def _resolve_rabbitmq_port() -> str:
    # Prefer explicit numeric port, but tolerate Kubernetes service-link values.
    raw = os.getenv("RABBITMQ_PORT_NUMBER") or os.getenv("RABBITMQ_PORT") or "5672"
    if raw.isdigit():
        return raw

    # Kubernetes service links often set values like: tcp://10.43.29.194:5672
    parsed = urlparse(raw)
    if parsed.port:
        return str(parsed.port)

    return "5672"

RABBITMQ_PORT = _resolve_rabbitmq_port()

broker_url = os.getenv(
    "CELERY_BROKER_URL",
    f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//",
)

celery_app = Celery("quantcloud", broker=broker_url, backend=None)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
