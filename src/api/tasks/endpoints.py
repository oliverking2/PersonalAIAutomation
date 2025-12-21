"""Endpoints for triggering and monitoring Celery tasks."""

import logging

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, status

from src.api.dependencies import verify_token
from src.api.tasks.models import (
    TaskStatusResponse,
    TaskTriggerRequest,
    TaskTriggerResponse,
)
from src.orchestration.celery_app import celery_app
from src.orchestration.tasks import process_newsletters_task, send_alerts_task

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/tasks",
    tags=["tasks"],
    dependencies=[Depends(verify_token)],
)


@router.post(
    "/process-newsletters",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger newsletter processing",
    description="Queues a Celery task to fetch and process newsletters.",
)
def trigger_process_newsletters(
    request: TaskTriggerRequest | None = None,
) -> TaskTriggerResponse:
    """Trigger the newsletter processing Celery task.

    :param request: Optional request body with processing parameters.
    :returns: Task trigger response with task ID.
    """
    days_back = request.days_back if request else 1

    logger.info(f"Triggering newsletter processing task (days_back={days_back})")
    result = process_newsletters_task.delay(days_back=days_back)

    return TaskTriggerResponse(
        task_id=result.id,
        task_name="process_newsletters_task",
        status="queued",
    )


@router.post(
    "/send-alerts",
    response_model=TaskTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger Telegram alerts",
    description="Queues a Celery task to send pending newsletter alerts.",
)
def trigger_send_alerts() -> TaskTriggerResponse:
    """Trigger the Telegram alerts Celery task.

    :returns: Task trigger response with task ID.
    """
    logger.info("Triggering send alerts task")
    result = send_alerts_task.delay()

    return TaskTriggerResponse(
        task_id=result.id,
        task_name="send_alerts_task",
        status="queued",
    )


@router.get(
    "/{task_id}",
    response_model=TaskStatusResponse,
    summary="Get task status",
    description="Retrieve the status and result of a previously triggered task.",
)
def get_task_status(task_id: str) -> TaskStatusResponse:
    """Get the status of a Celery task by ID.

    :param task_id: The Celery task identifier.
    :returns: Task status response.
    """
    logger.debug(f"Checking status for task_id={task_id}")

    result = AsyncResult(task_id, app=celery_app)

    task_result: dict[str, int | list[str]] | None = None
    if result.state == "SUCCESS" and result.result is not None:
        task_result = result.result

    return TaskStatusResponse(
        task_id=task_id,
        status=result.state,
        result=task_result,
    )
