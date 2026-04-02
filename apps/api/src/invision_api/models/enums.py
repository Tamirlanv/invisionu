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
    revision_required = "revision_required"
    screening_blocked = "screening_blocked"
    under_review = "under_review"
    interview_pending = "interview_pending"
    interview_scheduled = "interview_scheduled"
    interview_completed = "interview_completed"
    committee_review = "committee_review"
    pending_decision = "pending_decision"
    decision_made = "decision_made"
    waitlist = "waitlist"


class SectionKey(str, enum.Enum):
    personal = "personal"
    contact = "contact"
    education = "education"
    achievements_activities = "achievements_activities"
    leadership_evidence = "leadership_evidence"
    motivation_goals = "motivation_goals"
    growth_journey = "growth_journey"
    internal_test = "internal_test"
    social_status_cert = "social_status_cert"
    documents_manifest = "documents_manifest"
    consent_agreement = "consent_agreement"


class DocumentType(str, enum.Enum):
    certificate_of_social_status = "certificate_of_social_status"
    transcript = "transcript"
    portfolio = "portfolio"
    essay = "essay"
    supporting_documents = "supporting_documents"
    motivation_upload = "motivation_upload"
    growth_journey_upload = "growth_journey_upload"


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


class ExtractionStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class AnalysisRunStatus(str, enum.Enum):
    pending = "pending"
    completed = "completed"
    failed = "failed"
    skipped = "skipped"


class ScreeningResult(str, enum.Enum):
    passed = "passed"
    failed = "failed"
    revision_required = "revision_required"


class JobType(str, enum.Enum):
    extract_text = "extract_text"
    run_block_analysis = "run_block_analysis"
    initial_screening = "initial_screening"
    data_check_unit = "data_check_unit"


class JobStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    dead = "dead"


class DataCheckRunStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    partial = "partial"
    ready = "ready"
    failed = "failed"


class DataCheckUnitType(str, enum.Enum):
    test_profile_processing = "test_profile_processing"
    motivation_processing = "motivation_processing"
    growth_path_processing = "growth_path_processing"
    achievements_processing = "achievements_processing"
    link_validation = "link_validation"
    video_validation = "video_validation"
    certificate_validation = "certificate_validation"
    signals_aggregation = "signals_aggregation"
    candidate_ai_summary = "candidate_ai_summary"


class DataCheckUnitStatus(str, enum.Enum):
    pending = "pending"
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    manual_review_required = "manual_review_required"
