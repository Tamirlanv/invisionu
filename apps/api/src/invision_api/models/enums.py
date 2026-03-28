import enum


class RoleName(str, enum.Enum):
    candidate = "candidate"
    committee = "committee"
    admin = "admin"


class ApplicationStage(str, enum.Enum):
    application = "application"
    initial_screening = "initial_screening"
    application_review = "application_review"
    interview = "interview"
    committee_review = "committee_review"
    decision = "decision"


class ApplicationState(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    submitted = "submitted"
    under_screening = "under_screening"
    under_review = "under_review"
    interview_pending = "interview_pending"
    interview_completed = "interview_completed"
    committee_review = "committee_review"
    decision_made = "decision_made"


class SectionKey(str, enum.Enum):
    personal = "personal"
    contact = "contact"
    education = "education"
    internal_test = "internal_test"
    social_status_cert = "social_status_cert"


class DocumentType(str, enum.Enum):
    certificate_of_social_status = "certificate_of_social_status"
    transcript = "transcript"
    portfolio = "portfolio"
    essay = "essay"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class NotificationStatus(str, enum.Enum):
    pending = "pending"
    sent = "sent"
    failed = "failed"


class QuestionCategory(str, enum.Enum):
    logical_reasoning = "logical_reasoning"
    situational_judgement = "situational_judgement"
    self_reflection = "self_reflection"
    leadership_scenarios = "leadership_scenarios"


class QuestionType(str, enum.Enum):
    single_choice = "single_choice"
    multi_choice = "multi_choice"
    text = "text"


class StageActorType(str, enum.Enum):
    system = "system"
    user = "user"
    committee = "committee"


class VerificationType(str, enum.Enum):
    email = "email"
    identity = "identity"
    document = "document"


class CommitteeRecommendation(str, enum.Enum):
    admit = "admit"
    deny = "deny"
    waitlist = "waitlist"
    further_review = "further_review"


class AIDecisionAuthority(str, enum.Enum):
    human_only = "human_only"
