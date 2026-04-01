import { apiFetch } from "../api-client";
import { COMMISSION_STAGE_ORDER, COMMISSION_STAGE_TITLES } from "./constants";
import { sortColumnApplications } from "./sort";
import { getApplicationCardVisualState } from "./visual-state";
import type {
  CommissionBoardApplicationCard,
  CommissionBoardFilters,
  CommissionBoardMetrics,
  CommissionBoardResponse,
  CommissionApplicationDetailView,
  CommissionRange,
  CommissionRole,
  CommissionStage,
  CommissionUpdatesResponse,
} from "./types";

type ApiCard = Record<string, unknown>;

function toStage(v: unknown): CommissionStage {
  const s = String(v ?? "");
  if (s === "data_check" || s === "application_review" || s === "interview" || s === "committee_decision" || s === "result") {
    return s;
  }
  return "result";
}

function asStr(v: unknown): string | null {
  if (v == null) return null;
  const s = String(v);
  return s.length ? s : null;
}

function asNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v === "string" && v.trim()) {
    const n = Number(v);
    if (Number.isFinite(n)) return n;
  }
  return null;
}

function asBool(v: unknown): boolean {
  return Boolean(v);
}

export function mapApiCard(card: ApiCard): CommissionBoardApplicationCard {
  const currentStage = toStage(card.stage_column ?? card.currentStage);
  const currentStageStatus = asStr(card.stage_status ?? card.currentStageStatus) as CommissionBoardApplicationCard["currentStageStatus"];
  const finalDecision = asStr(card.final_decision ?? card.finalDecision) as CommissionBoardApplicationCard["finalDecision"];
  const manualAttentionFlag = asBool(card.attention_flag_manual ?? card.manualAttentionFlag);

  return {
    applicationId: String(card.application_id ?? card.applicationId ?? ""),
    candidateId: String(card.application_id ?? card.applicationId ?? ""),
    candidateFullName: String(card.candidate_full_name ?? card.candidateFullName ?? ""),
    program: String(card.program ?? ""),
    city: asStr(card.city),
    phone: asStr(card.phone),
    age: asNum(card.age),
    submittedAt: asStr(card.submitted_at_iso ?? card.submittedAt),
    updatedAt: asStr(card.updated_at_iso ?? card.updatedAt),
    currentStage,
    currentStageStatus,
    finalDecision,
    manualAttentionFlag,
    commentCount: asNum(card.comment_count ?? card.commentCount) ?? 0,
    aiRecommendation: asStr(card.ai_recommendation ?? card.aiRecommendation) as CommissionBoardApplicationCard["aiRecommendation"],
    aiConfidence: asNum(card.ai_confidence ?? card.aiConfidence),
    visualState: getApplicationCardVisualState({ currentStageStatus, finalDecision, manualAttentionFlag }),
  };
}

function toParams(filters: CommissionBoardFilters): URLSearchParams {
  const p = new URLSearchParams();
  if (filters.search.trim()) p.set("search", filters.search.trim());
  if (filters.program) p.set("program", filters.program);
  return p;
}

function defaultMetrics(cards: CommissionBoardApplicationCard[]): CommissionBoardMetrics {
  const today = new Date();
  const todayIso = `${today.getUTCFullYear()}-${String(today.getUTCMonth() + 1).padStart(2, "0")}-${String(today.getUTCDate()).padStart(2, "0")}`;
  return {
    totalApplications: cards.length,
    todayApplications: cards.filter((c) => (c.submittedAt ?? "").startsWith(todayIso)).length,
    needsAttention: cards.filter((c) => c.currentStageStatus === "needs_attention" || c.manualAttentionFlag).length,
    aiRecommended: cards.filter((c) => c.aiRecommendation === "recommend").length,
  };
}

export async function getBoardMetrics(filters: CommissionBoardFilters): Promise<CommissionBoardMetrics> {
  try {
    const params = new URLSearchParams();
    params.set("range", filters.range);
    if (filters.search.trim()) params.set("search", filters.search.trim());
    if (filters.program) params.set("program", filters.program);
    return await apiFetch<CommissionBoardMetrics>(`/commission/metrics?${params.toString()}`);
  } catch {
    // Fallback for old backend contract.
    const rows = await apiFetch<ApiCard[]>(`/commission/applications?${toParams(filters).toString()}`);
    const cards = rows.map(mapApiCard);
    return defaultMetrics(cards);
  }
}

export async function getCommissionBoard(filters: CommissionBoardFilters): Promise<CommissionBoardResponse> {
  const rows = await apiFetch<ApiCard[]>(`/commission/applications?${toParams(filters).toString()}`);
  const cards = rows.map(mapApiCard);

  const columns = COMMISSION_STAGE_ORDER.map((stage) => ({
    stage,
    title: COMMISSION_STAGE_TITLES[stage],
    applications: sortColumnApplications(cards.filter((c) => c.currentStage === stage)),
  }));

  const metrics = await getBoardMetrics(filters);
  return { filters, columns, metrics };
}

export async function getCommissionRole(): Promise<CommissionRole | null> {
  try {
    const data = await apiFetch<{ role: CommissionRole | null }>("/commission/me");
    return data.role;
  } catch {
    return null;
  }
}

export async function moveApplicationToNextStage(applicationId: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/stage/advance`, {
    method: "POST",
    json: { reason_comment: reasonComment ?? null },
  });
}

export async function createQuickComment(applicationId: string, body: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/comments`, {
    method: "POST",
    json: { body },
  });
}

export async function setAttentionFlag(applicationId: string, value: boolean, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/attention`, {
    method: "PATCH",
    json: { value, reason_comment: reasonComment ?? null },
  });
}

export async function getUpdates(cursor: string | null): Promise<CommissionUpdatesResponse> {
  const q = cursor ? `?cursor=${encodeURIComponent(cursor)}` : "";
  return await apiFetch<CommissionUpdatesResponse>(`/commission/updates${q}`);
}

export function rangeFromQuery(v: string | null): CommissionRange {
  if (v === "day" || v === "week" || v === "month" || v === "year") return v;
  return "week";
}

export async function getCommissionApplicationDetail(applicationId: string): Promise<CommissionApplicationDetailView> {
  return await apiFetch<CommissionApplicationDetailView>(`/commission/applications/${applicationId}`);
}

export async function getApplicationAuditPreview(applicationId: string): Promise<CommissionApplicationDetailView["recentActivity"]> {
  return await apiFetch<CommissionApplicationDetailView["recentActivity"]>(`/commission/applications/${applicationId}/audit`);
}

export async function updateStageStatus(applicationId: string, status: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/stage-status`, {
    method: "PATCH",
    json: { status, reason_comment: reasonComment ?? null },
  });
}

export async function setFinalDecision(applicationId: string, finalDecision: string, reasonComment?: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/final-decision`, {
    method: "POST",
    json: { final_decision: finalDecision, reason_comment: reasonComment ?? null },
  });
}

export async function setRubricScores(
  applicationId: string,
  items: Array<{ rubric: string; score: string }>,
  comment?: string,
): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/rubric`, {
    method: "PUT",
    json: { items, comment: comment ?? null },
  });
}

export async function setInternalRecommendation(
  applicationId: string,
  recommendation: string,
  reasonComment?: string,
): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/internal-recommendation`, {
    method: "PUT",
    json: { recommendation, reason_comment: reasonComment ?? null },
  });
}

export async function createApplicationComment(applicationId: string, body: string): Promise<void> {
  await apiFetch(`/commission/applications/${applicationId}/comments`, {
    method: "POST",
    json: { body },
  });
}

