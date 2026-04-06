from celery import Celery
import os

RABBITMQ_USER = os.getenv("RABBITMQ_USER", "quant")
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "changeme")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq.quant-cloud.svc.cluster.local")
RABBITMQ_PORT = os.getenv("RABBITMQ_PORT", "5672")

broker_url = f"amqp://{RABBITMQ_USER}:{RABBITMQ_PASSWORD}@{RABBITMQ_HOST}:{RABBITMQ_PORT}//"

celery_app = Celery("quantcloud", broker=broker_url, backend=None)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)
