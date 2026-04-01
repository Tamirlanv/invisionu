import { COMMISSION_STAGE_ORDER } from "./constants";
import type { CommissionRole, CommissionStage } from "./types";

export function canMoveCards(role: CommissionRole | null): boolean {
  return role === "reviewer" || role === "admin";
}

export function isNextStageOnly(from: CommissionStage, to: CommissionStage): boolean {
  const i = COMMISSION_STAGE_ORDER.indexOf(from);
  const j = COMMISSION_STAGE_ORDER.indexOf(to);
  if (i < 0 || j < 0) return false;
  return j === i + 1;
}

