import mimetypes
from uuid import UUID

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from invision_api.core.config import get_settings
from invision_api.models.application import Document
from invision_api.models.enums import DocumentType, VerificationStatus
from invision_api.models.user import User
from invision_api.services import application_service
from invision_api.services.storage import get_storage

ALLOWED_MIME: dict[str, tuple[str, ...]] = {
    DocumentType.certificate_of_social_status.value: (
        "application/pdf",
        "image/jpeg",
        "image/png",
    ),
    DocumentType.transcript.value: ("application/pdf",),
    DocumentType.portfolio.value: ("application/pdf", "image/jpeg", "image/png"),
    DocumentType.essay.value: ("application/pdf",),
}

MAX_BYTES: dict[str, int] = {
    DocumentType.certificate_of_social_status.value: 10 * 1024 * 1024,
    DocumentType.transcript.value: 15 * 1024 * 1024,
    DocumentType.portfolio.value: 40 * 1024 * 1024,
    DocumentType.essay.value: 10 * 1024 * 1024,
}


def _validate_file(document_type: DocumentType, filename: str, content_type: str | None, size: int) -> str:
    allowed = ALLOWED_MIME.get(document_type.value)
    if not allowed:
        raise HTTPException(status_code=400, detail="Неподдерживаемый тип документа")
    ct = (content_type or mimetypes.guess_type(filename)[0] or "").split(";")[0].strip()
    if ct not in allowed:
        raise HTTPException(status_code=400, detail=f"Неподдерживаемый тип файла для {document_type.value}: {ct}")
    max_b = MAX_BYTES.get(document_type.value, get_settings().max_upload_bytes_default)
    if size > max_b:
        raise HTTPException(status_code=400, detail="Файл слишком большой")
    return ct


async def upload_document(
    db: Session,
    user: User,
    application_id: UUID,
    document_type: DocumentType,
    file: UploadFile,
) -> Document:
    _, app = application_service.get_profile_and_application(db, user)
    if app.id != application_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Заявление не найдено")
    application_service._ensure_editable(app)  # noqa: SLF001

    raw = await file.read()
    size = len(raw)
    ct = _validate_file(document_type, file.filename or "upload.bin", file.content_type, size)

    storage = get_storage()
    key = storage.put(
        application_id=app.id,
        original_filename=file.filename or "upload.bin",
        data=raw,
        content_type=ct,
    )

    doc = Document(
        application_id=app.id,
        uploaded_by_user_id=user.id,
        document_type=document_type.value,
        storage_key=key,
        original_filename=file.filename or "upload.bin",
        mime_type=ct,
        byte_size=size,
        verification_status=VerificationStatus.pending.value,
    )
    db.add(doc)
    db.flush()
    if document_type == DocumentType.certificate_of_social_status:
        application_service.recompute_social_section(db, app)
    db.commit()
    db.refresh(doc)
    return doc
