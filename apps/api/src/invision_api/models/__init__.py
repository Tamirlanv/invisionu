"""ORM models — import all for Alembic metadata."""

from invision_api.models.application import (  # noqa: F401
    AIReviewMetadata,
    AdmissionDecision,
    AnalysisJob,
    Application,
    ApplicationReviewSnapshot,
    ApplicationSectionState,
    ApplicationStageHistory,
    AuditLog,
    CandidateProfile,
    CommitteeReview,
    Document,
    DocumentExtraction,
    EducationRecord,
    InitialScreeningResult,
    InternalTestAnswer,
    InternalTestQuestion,
    InterviewSession,
    Notification,
    TextAnalysisRun,
    VerificationRecord,
)
from invision_api.models.commission import (  # noqa: F401
    ApplicationComment,
    ApplicationCommentTag,
    ApplicationCommissionProjection,
    ApplicationStageState,
    ApplicationStageStatusHistory,
    ApplicationTag,
    ApplicationTagLink,
    CommentTag,
    CommissionUser,
    ExportJob,
    InternalRecommendationRow,
    ReviewRubricScore,
)
from invision_api.models.link_validation import LinkValidationResultRow  # noqa: F401
from invision_api.models.certificate_validation import CertificateValidationResultRow  # noqa: F401
from invision_api.models.candidate_validation_orchestration import (  # noqa: F401
    CandidateValidationAuditEvent,
    CandidateValidationCheck,
    CandidateValidationRun,
)
from invision_api.models.video_validation import VideoValidationResultRow  # noqa: F401
from invision_api.models.user import Role, User, UserRole  # noqa: F401
