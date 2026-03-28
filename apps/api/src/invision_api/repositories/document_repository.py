from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from invision_api.models.application import Document


def list_documents_for_application(db: Session, application_id: UUID) -> list[Document]:
    return list(db.scalars(select(Document).where(Document.application_id == application_id)).all())


def has_document_type(db: Session, application_id: UUID, document_type: str) -> bool:
    return (
        db.scalar(
            select(Document.id).where(
                Document.application_id == application_id,
                Document.document_type == document_type,
            ).limit(1)
        )
        is not None
    )
