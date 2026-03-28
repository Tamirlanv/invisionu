from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from invision_api.api.deps import require_roles
from invision_api.db.session import get_db
from invision_api.models.enums import DocumentType, RoleName
from invision_api.models.user import User
from invision_api.services import document_service

router = APIRouter()


@router.post("/upload")
async def upload(
    application_id: UUID = Form(...),
    document_type: DocumentType = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(require_roles(RoleName.candidate)),
    db: Session = Depends(get_db),
) -> dict:
    doc = await document_service.upload_document(db, user, application_id, document_type, file)
    return {
        "id": str(doc.id),
        "application_id": str(doc.application_id),
        "document_type": doc.document_type,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "byte_size": doc.byte_size,
        "verification_status": doc.verification_status,
        "created_at": doc.created_at.isoformat(),
    }
