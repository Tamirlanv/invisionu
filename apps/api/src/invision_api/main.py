import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from invision_api.api.v1.router import api_router
from invision_api.core.config import get_settings

_EXPECTED_INTERNAL_TEST_QUESTIONS = 40


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    log = logging.getLogger("uvicorn.error")
    try:
        from invision_api.db.session import SessionLocal
        from invision_api.repositories import internal_test_repository

        db = SessionLocal()
        try:
            n = internal_test_repository.count_active_questions(db)
            if n != _EXPECTED_INTERNAL_TEST_QUESTIONS:
                log.warning(
                    "internal_test_questions: expected %s active questions, found %s (run seed or check DB)",
                    _EXPECTED_INTERNAL_TEST_QUESTIONS,
                    n,
                )
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — startup must not crash if DB unreachable briefly
        log.warning("internal_test_questions startup check failed: %s", exc)

    try:
        from invision_api.db.session import SessionLocal
        from invision_api.services.commission_bootstrap import ensure_commission_user_from_env

        db = SessionLocal()
        try:
            ensure_commission_user_from_env(db, get_settings())
        finally:
            db.close()
    except Exception as exc:  # noqa: BLE001 — startup must not crash if DB unreachable briefly
        log.warning("commission_bootstrap startup failed: %s", exc)

    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="inVision U Admissions API",
        version="1.0.0",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=_lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
