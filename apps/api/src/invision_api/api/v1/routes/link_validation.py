from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import RoleName
from invision_api.models.user import User
from invision_api.services.link_validation.service import validate_candidate_link
from invision_api.services.link_validation.types import LinkValidationRequest, LinkValidationResult

router = APIRouter()


@router.post("/validate", response_model=LinkValidationResult)
def validate_link(
    payload: LinkValidationRequest,
    user: User = Depends(require_roles(RoleName.candidate, RoleName.committee, RoleName.admin)),
    db: Session = Depends(get_db),
) -> LinkValidationResult:
    _ = user
    return validate_candidate_link(db, payload)
