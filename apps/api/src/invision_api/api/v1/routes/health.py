from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from invision_api.core.redis_client import redis_ping
from invision_api.db.session import get_db

router = APIRouter()


@router.get("/health")
def health(db: Session = Depends(get_db)) -> dict:
    db_ok = True
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok and redis_ping() else "degraded",
        "database": "ok" if db_ok else "error",
        "redis": "ok" if redis_ping() else "error",
    }
