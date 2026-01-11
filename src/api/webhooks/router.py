"""Router for webhook endpoints."""

from fastapi import APIRouter

from src.api.webhooks.glitchtip import router as glitchtip_router

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

router.include_router(glitchtip_router)
