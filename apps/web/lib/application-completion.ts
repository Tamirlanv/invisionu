import { sectionKeyRu } from "./labels";

export type SectionCompletionStatus = "complete" | "incomplete" | "empty";

export type ReviewSectionState = {
  is_complete: boolean;
  payload?: unknown;
};

export type ApplicationCompletionItem = {
  sectionKey: string;
  title: string;
  status: SectionCompletionStatus;
};

export type ApplicationCompletionSummary = {
  percent: number;
  sections: ApplicationCompletionItem[];
  completeCount: number;
  incompleteCount: number;
  emptyCount: number;
  missingSections: string[];
  locked: boolean;
  emailVerified: boolean;
  canSubmit: boolean;
};

type CompletionInput = {
  requiredSections: string[];
  missingSections: string[];
  sections: Record<string, ReviewSectionState>;
  locked: boolean;
  emailVerified: boolean;
};

function isEmptyPrimitive(value: unknown): boolean {
  if (value === null || value === undefined) return true;
  if (typeof value === "string") return value.trim().length === 0;
  if (typeof value === "boolean") return value === false;
  return false;
}

export function isSectionPayloadEmpty(payload: unknown): boolean {
  if (isEmptyPrimitive(payload)) return true;
  if (typeof payload === "number" || typeof payload === "bigint") return false;

  if (Array.isArray(payload)) {
    if (payload.length === 0) return true;
    return payload.every((item) => isSectionPayloadEmpty(item));
  }

  if (typeof payload === "object") {
    const values = Object.values(payload as Record<string, unknown>);
    if (values.length === 0) return true;
    return values.every((value) => isSectionPayloadEmpty(value));
  }

  return false;
}

export function getSectionCompletionStatus(
  sectionKey: string,
  sections: Record<string, ReviewSectionState>,
  missingSections: Set<string>,
): SectionCompletionStatus {
  const section = sections[sectionKey];
  if (!section) return "empty";
  if (missingSections.has(sectionKey)) {
    return isSectionPayloadEmpty(section.payload) ? "empty" : "incomplete";
  }
  if (section.is_complete) return "complete";
  if (isSectionPayloadEmpty(section.payload)) return "empty";
  return "incomplete";
}

export function calculateCompletionPercent(completeCount: number, requiredTotal: number): number {
  if (requiredTotal <= 0) return 0;
  return Math.round((completeCount / requiredTotal) * 100);
}

export function getApplicationCompletionSummary(input: CompletionInput): ApplicationCompletionSummary {
  const missingSet = new Set(input.missingSections);
  const sections = input.requiredSections.map((sectionKey) => ({
    sectionKey,
    title: sectionKeyRu(sectionKey),
    status: getSectionCompletionStatus(sectionKey, input.sections, missingSet),
  }));

  const completeCount = sections.filter((section) => section.status === "complete").length;
  const incompleteCount = sections.filter((section) => section.status === "incomplete").length;
  const emptyCount = sections.filter((section) => section.status === "empty").length;

  const percent = calculateCompletionPercent(completeCount, input.requiredSections.length);
  const canSubmit =
    percent >= 100 &&
    incompleteCount === 0 &&
    emptyCount === 0 &&
    input.missingSections.length === 0 &&
    !input.locked &&
    input.emailVerified;

  return {
    percent,
    sections,
    completeCount,
    incompleteCount,
    emptyCount,
    missingSections: input.missingSections,
    locked: input.locked,
    emailVerified: input.emailVerified,
    canSubmit,
  };
}
