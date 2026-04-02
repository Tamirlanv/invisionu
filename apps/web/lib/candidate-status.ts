export type CandidateApplicationStatus = {
  current_stage: string;
  submission_state: {
    state: string;
    submitted_at: string | null;
    locked: boolean;
    queue_status?: "ready" | "degraded" | string;
    queue_failures_count?: number;
    queue_message?: string | null;
  };
  stage_history: Array<{
    from_stage?: string | null;
    to_stage: string;
    entered_at: string;
    exited_at?: string | null;
    candidate_visible_note?: string | null;
  }>;
  stage_descriptions: Record<string, string>;
};

export function isDataVerificationStage(status: CandidateApplicationStatus | null): boolean {
  return status?.current_stage === "initial_screening";
}

export function getLatestCandidateVisibleNote(status: CandidateApplicationStatus | null): string | null {
  if (!status?.stage_history?.length) return null;
  for (let i = status.stage_history.length - 1; i >= 0; i -= 1) {
    const note = status.stage_history[i]?.candidate_visible_note?.trim();
    if (note) return note;
  }
  return null;
}
