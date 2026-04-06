from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from celery.result import AsyncResult
import os

from app.worker.celery_app import celery_app
from app.worker.tasks import run_pricing_job

app = FastAPI(title="Quant Cloud API")

API_KEY = os.getenv("API_KEY", "20398570121")

class JobRequest(BaseModel):
    job_type: str
    sleep_seconds: int = 10

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/jobs")
def submit_job(job: JobRequest, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    task = run_pricing_job.delay(job.model_dump())
    return {"task_id": task.id, "status": "queued"}

@app.get("/jobs/{task_id}")
def get_job(task_id: str, x_api_key: str = Header(default="")):
    if x_api_key != API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")

    result = AsyncResult(task_id, app=celery_app)
    response = {"task_id": task.id, "state": result.state}

    if result.ready():
        try:
            response["result"] = result.result
        except Exception as exc:
            response["error"] = str(exc)

    return response
