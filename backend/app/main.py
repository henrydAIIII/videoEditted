from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.health import router as health_router
from app.api.routes.upload import router as upload_router


def create_app() -> FastAPI:
    app = FastAPI(title="Video Editted Backend")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api_router_prefix = "/api"
    app.include_router(health_router, prefix=api_router_prefix)
    app.include_router(upload_router, prefix=api_router_prefix)

    return app


app = create_app()

