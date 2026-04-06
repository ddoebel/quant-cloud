from .celery_app import celery_app
import time

@celery_app.task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 3})
def run_pricing_job(self, payload: dict):
    seconds = int(payload.get("sleep_seconds", 10))
    time.sleep(seconds)
    return {
        "status": "ok",
        "job_type": payload.get("job_type", "demo"),
        "sleep_seconds": seconds,
    }
