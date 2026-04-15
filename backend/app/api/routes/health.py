from fastapi import APIRouter

from app.core.config import get_settings
from app.core.responses import success_response

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    settings = get_settings()
    return success_response(
        {
            "status": "ok",
            "service": settings.service_name,
        }
    )

