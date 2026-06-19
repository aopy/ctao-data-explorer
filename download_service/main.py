from __future__ import annotations

import logging

from ctao_shared.logging_config import setup_logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from download_service.router import router
from download_service.service import RequestStatusStore

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    setup_logging()

    app = FastAPI(
        title="CTAO Download Service",
        description="Token-only file-scoped download service",
        version="0.1.0",
    )

    app.state.download_status_store = RequestStatusStore()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:8000",
            "http://127.0.0.1:8000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("download_service.main:app", host="127.0.0.1", port=8002, reload=True)
