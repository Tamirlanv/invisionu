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

export type ValidationCheckResult = {
  status: string;
  result: Record<string, unknown> | null;
  updatedAt: string | null;
};

export type ValidationReport = {
  runId: string;
  candidateId: string;
  applicationId: string;
  overallStatus: string;
  checks: {
    links: ValidationCheckResult | null;
    videoPresentation: ValidationCheckResult | null;
    certificates: ValidationCheckResult | null;
  };
  warnings: string[];
  errors: string[];
  explainability: string[];
  updatedAt: string | null;
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
  achievements: Record<string, unknown> | null;
  aiSummary: ApplicationAISummaryView | null;
  validationReport?: ValidationReport | null;
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

export type CommissionApplicationPersonalInfoView = {
  applicationId: string;
  candidateSummary: {
    fullName: string;
    program: string | null;
    phone: string | null;
    telegram: string | null;
    instagram: string | null;
    submittedAt: string | null;
    currentStage: CommissionStage | string;
    currentStageStatus: StageStatus | string;
  };
  aiSummary: {
    profileTitle: string | null;
    summaryText: string | null;
    strengths: string[];
    weakPoints: string[];
  } | null;
  stageContext: {
    currentStage: CommissionStage | string;
    currentStageStatus: StageStatus | string;
    availableActions: string[];
  };
  personalInfo: {
    basicInfo: {
      fullName: string;
      gender: string | null;
      birthDate: string | null;
      age: number | null;
    };
    guardians: Array<{
      role: string;
      fullName: string;
      phone: string | null;
    }>;
    address: {
      country: string | null;
      region: string | null;
      city: string | null;
      fullAddress: string | null;
    };
    contacts: {
      phone: string | null;
      instagram: string | null;
      telegram: string | null;
      whatsapp: string | null;
    };
    documents: Array<{
      id: string;
      type: string;
      fileName: string;
      fileSize: string | null;
      fileUrl: string | null;
      fileRef: string | null;
    }>;
    videoPresentation: {
      url: string;
    } | null;
  };
  motivation: {
    narrative: string | null;
  };
  path: Array<{
    questionTitle: string;
    description: string;
    text: string;
  }> | null;
  achievements: {
    text: string | null;
    role: string | null;
    year: string | null;
    links: Array<{
      label: string;
      url: string;
      linkType: string | null;
    }>;
  };
  processingStatus: {
    overall: "pending" | "running" | "partial" | "ready" | "failed";
    completedCount: number;
    totalCount: number;
    units: Record<string, string>;
    manualReviewRequired: boolean;
    warnings: string[];
    errors: string[];
  } | null;
  comments: Array<{
    id: string;
    text: string;
    authorName: string;
    createdAt: string | null;
  }>;
  actions: {
    canComment: boolean;
    canMoveForward: boolean;
  };
};

export type CommissionApplicationTestInfoView = {
  personalityProfile: {
    profileType: string;
    profileTitle: string;
    summary: string;
    rawScores: Record<string, number>;
    ranking: Array<{ trait: string; score: number }>;
    dominantTrait: string;
    secondaryTrait: string;
    weakestTrait: string;
    flags?: Record<string, boolean>;
    meta?: Record<string, unknown>;
  } | null;
  testLang: string;
  questions: Array<{
    index: number;
    questionId: string;
    prompt: string;
    selectedAnswer: string | null;
  }>;
  aiSummary: {
    aboutCandidate: string | null;
    weakPoints: string[];
  } | null;
};

export type SidebarSection = {
  title: string;
  items: string[];
};

export type CommissionSidebarPanelView = {
  type: "validation" | "summary";
  title: string;
  sections: SidebarSection[];
};

export type ReviewScoreItem = {
  key: string;
  label: string;
  recommendedScore: number;
  manualScore: number | null;
  effectiveScore: number;
};

export type ReviewScoreBlock = {
  section: string;
  items: ReviewScoreItem[];
  totalScore: number;
  maxTotalScore: number;
};

