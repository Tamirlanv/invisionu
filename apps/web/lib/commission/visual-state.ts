import type { CardVisualState, FinalDecision, StageStatus } from "./types";

type Input = {
  currentStageStatus: StageStatus | null;
  finalDecision: FinalDecision | null;
  manualAttentionFlag: boolean;
};

export function getApplicationCardVisualState(v: Input): CardVisualState {
  if (v.manualAttentionFlag || v.currentStageStatus === "needs_attention") return "attention";

  if (v.finalDecision) {
    if (v.finalDecision === "reject") return "negative";
    if (v.finalDecision === "waitlist") return "neutral";
    return "positive";
  }

  if (v.currentStageStatus === "approved") return "positive";
  if (v.currentStageStatus === "rejected") return "negative";
  return "neutral";
}

