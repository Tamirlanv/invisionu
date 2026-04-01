import type { CommissionBoardApplicationCard } from "./types";

function ts(s: string | null): number {
  if (!s) return 0;
  const t = Date.parse(s);
  return Number.isFinite(t) ? t : 0;
}

function attentionRank(c: CommissionBoardApplicationCard): number {
  if (c.currentStageStatus === "needs_attention" || c.manualAttentionFlag) return 0;
  return 1;
}

export function sortColumnApplications(rows: CommissionBoardApplicationCard[]): CommissionBoardApplicationCard[] {
  return [...rows].sort((a, b) => {
    const r1 = attentionRank(a) - attentionRank(b);
    if (r1 !== 0) return r1;

    const r2 = ts(b.submittedAt) - ts(a.submittedAt);
    if (r2 !== 0) return r2;

    const r3 = ts(b.updatedAt) - ts(a.updatedAt);
    if (r3 !== 0) return r3;

    return a.applicationId.localeCompare(b.applicationId);
  });
}

