from fastapi import APIRouter

from invision_api.api.v1.routes import (
    auth,
    candidates,
    commission,
    documents,
    health,
    internal_admissions,
    internal_test,
    link_validation,
)

api_router = APIRouter()
api_router.include_router(health.router, tags=["health"])
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(candidates.router, prefix="/candidates", tags=["candidates"])
api_router.include_router(internal_test.router, prefix="/internal-test", tags=["internal-test"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(
    internal_admissions.router,
    prefix="/internal/admissions",
    tags=["internal-admissions"],
)
api_router.include_router(commission.router, prefix="/commission", tags=["commission"])
api_router.include_router(link_validation.router, prefix="/links", tags=["link-validation"])
