export type CommissionRange = "day" | "week" | "month" | "year";

export type CommissionRole = "viewer" | "reviewer" | "admin";

export type CommissionStage =
  | "data_check"
  | "application_review"
  | "interview"
  | "committee_decision"
  | "result";

export type StageStatus = "new" | "in_review" | "needs_attention" | "approved" | "rejected";
export type FinalDecision = "move_forward" | "reject" | "waitlist" | "invite_interview" | "enrolled";
export type AIRecommendation = "recommend" | "neutral" | "caution";

export type CardVisualState = "positive" | "negative" | "neutral" | "attention";

export type CommissionBoardApplicationCard = {
  applicationId: string;
  candidateId: string;
  candidateFullName: string;
  program: string;
  city: string | null;
  phone: string | null;
  age: number | null;
  submittedAt: string | null;
  updatedAt: string | null;
  currentStage: CommissionStage;
  currentStageStatus: StageStatus | null;
  finalDecision: FinalDecision | null;
  manualAttentionFlag: boolean;
  commentCount: number;
  aiRecommendation: AIRecommendation | null;
  aiConfidence: number | null;
  visualState: CardVisualState;
};

export type CommissionBoardColumn = {
  stage: CommissionStage;
  title: string;
  applications: CommissionBoardApplicationCard[];
};

export type CommissionBoardMetrics = {
  totalApplications: number;
  todayApplications: number;
  needsAttention: number;
  aiRecommended: number;
};

export type CommissionBoardFilters = {
  search: string;
  program: string | null;
  range: CommissionRange;
};

export type CommissionBoardResponse = {
  filters: CommissionBoardFilters;
  metrics: CommissionBoardMetrics;
  columns: CommissionBoardColumn[];
};

export type CommissionUpdatesResponse = {
  changedApplicationIds: string[];
  latestCursor: string;
};

export type ApplicationAISummaryView = {
  summaryText: string | null;
  strengths: string[];
  weakPoints: string[];
  leadershipSignals: string[];
  missionFitNotes: string[];
  redFlags: string[];
  recommendation: AIRecommendation | null;
  confidenceScore: number | null;
  explainabilityNotes: string[];
  generatedAt: string | null;
  status: "not_generated" | "ready" | "failed";
};

export type CommissionApplicationDetailView = {
  application_id: string;
  submitted_at: string | null;
  candidate: {
    full_name: string;
    city: string | null;
    phone: string | null;
    program: string | null;
    age: number | null;
  };
  stage: {
    currentStage: CommissionStage;
    currentStageStatus: StageStatus;
    finalDecision: FinalDecision | null;
    availableNextActions: string[];
  };
  personalInfo: {
    basicInfo: Record<string, unknown>;
    contacts: Record<string, unknown>;
    guardians: Array<Record<string, unknown>>;
    address: Record<string, unknown>;
    education: Record<string, unknown>;
  };
  test: Record<string, unknown> | null;
  motivation: Record<string, unknown> | null;
  path: {
    answers: Array<{ questionKey: string; questionTitle: string; text: string }>;
    summary?: string | null;
    keyThemes?: string[] | null;
  } | null;
  portfolio: Record<string, unknown> | null;
  essay: Record<string, unknown> | null;
  aiSummary: ApplicationAISummaryView | null;
  review: {
    rubricScores: Array<{
      criterion: string;
      value: "strong" | "medium" | "low";
      authorId: string;
      updatedAt: string;
    }>;
    internalRecommendations: Array<{
      authorId: string;
      recommendation: "recommend_forward" | "needs_discussion" | "reject";
      reasonComment: string | null;
      updatedAt: string;
    }>;
    tags: string[];
  };
  comments: Array<{
    id: string;
    text: string;
    authorId: string | null;
    createdAt: string | null;
    tags: string[];
  }>;
  recentActivity: Array<{
    id: string;
    event_type: string;
    timestamp: string;
    actor_user_id: string | null;
    previous_value: unknown;
    next_value: unknown;
    metadata: unknown;
  }>;
};

