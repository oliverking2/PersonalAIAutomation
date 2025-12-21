"""Celery application configuration."""

import os

from celery import Celery

# Redis URL for broker and result backend
REDIS_URL = os.environ["REDIS_URL"]

celery_app = Celery(
    "newsletter_automation",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["src.orchestration.tasks"],
)

# Celery configuration
celery_app.conf.update(
    # Task execution settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Retry settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Result expiration (24 hours)
    result_expires=86400,
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_concurrency=2,
)
