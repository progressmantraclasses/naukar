"""Redis-backed durable queue adapter for long-running orchestration."""
import asyncio

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "naukar",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)
celery_app.conf.update(
    task_track_started=True,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
)


@celery_app.task(
    bind=True,
    autoretry_for=(ConnectionError, TimeoutError),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def run_orchestration_job(self, task_id: str, user_input: str, user_id: str):
    from app.core.database import AsyncSessionLocal
    from app.orchestrator.executive import ExecutiveOrchestrator

    async def run():
        async with AsyncSessionLocal() as db:
            await ExecutiveOrchestrator(db).run(task_id, user_input, user_id=user_id)

    return asyncio.run(run())


def enqueue_orchestration(task_id: str, user_input: str, user_id: str):
    return run_orchestration_job.delay(task_id, user_input, user_id)
