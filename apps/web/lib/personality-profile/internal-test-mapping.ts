import type { AnswerKey, Question } from "./types";

export type ServerInternalTestQuestion = {
  id: string;
  display_order: number;
  question_type: string;
};

export type PersonalityQuestionMappings =
  | {
      ok: true;
      uiToServer: Map<string, string>;
      serverToUi: Map<string, string>;
    }
  | { ok: false; error: string };

const MISMATCH = "Тест временно недоступен: рассинхрон вопросов.";

/**
 * Pair static UI questions with GET /internal-test/questions by sorted display_order.
 * Server is the source of truth for IDs used in POST /internal-test/answers.
 */
export function buildPersonalityQuestionMappings(
  uiQuestions: readonly Question[],
  serverQuestions: ServerInternalTestQuestion[],
): PersonalityQuestionMappings {
  if (!serverQuestions.length) {
    return { ok: false, error: MISMATCH };
  }
  const sorted = [...serverQuestions].sort((a, b) => {
    if (a.display_order !== b.display_order) {
      return a.display_order - b.display_order;
    }
    return a.id.localeCompare(b.id);
  });
  if (sorted.length !== uiQuestions.length) {
    return { ok: false, error: MISMATCH };
  }
  for (const sq of sorted) {
    if (sq.question_type !== "single_choice" && sq.question_type !== "multi_choice") {
      return { ok: false, error: MISMATCH };
    }
  }
  const uiToServer = new Map<string, string>();
  const serverToUi = new Map<string, string>();
  for (let i = 0; i < uiQuestions.length; i++) {
    const ui = uiQuestions[i];
    const sv = sorted[i];
    uiToServer.set(ui.id, sv.id);
    serverToUi.set(sv.id, ui.id);
  }
  return { ok: true, uiToServer, serverToUi };
}

export function mapServerAnswersToUiRecord(
  serverToUi: Map<string, string>,
  savedAnswers: Array<{
    question_id: string;
    selected_options?: string[] | null;
  }>,
): Record<string, AnswerKey | undefined> {
  const acc: Record<string, AnswerKey | undefined> = {};
  for (const item of savedAnswers) {
    const uiId = serverToUi.get(item.question_id);
    if (!uiId) continue;
    const first = item.selected_options?.[0];
    if (first && ["A", "B", "C", "D"].includes(first)) {
      acc[uiId] = first as AnswerKey;
    }
  }
  return acc;
}

export function buildInternalTestAnswerPayload(
  questions: readonly Question[],
  answers: Record<string, AnswerKey | undefined>,
  uiToServer: Map<string, string>,
): Array<{ question_id: string; selected_options: AnswerKey[] }> {
  const out: Array<{ question_id: string; selected_options: AnswerKey[] }> = [];
  for (const q of questions) {
    const key = answers[q.id];
    if (!key) continue;
    const serverId = uiToServer.get(q.id);
    if (!serverId) continue;
    out.push({ question_id: serverId, selected_options: [key] });
  }
  return out;
}
