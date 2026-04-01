import type { GrowthQuestionId } from "./constants";

export type GrowthAnswerMetaState = {
  was_pasted: boolean;
  paste_count: number;
  last_pasted_at: string | null;
  typing_count: number;
  typing_duration_ms: number;
  was_edited_after_paste: boolean;
  delete_count: number;
  revision_count: number;
};

export const DEFAULT_GROWTH_ANSWER_META: GrowthAnswerMetaState = {
  was_pasted: false,
  paste_count: 0,
  last_pasted_at: null,
  typing_count: 0,
  typing_duration_ms: 0,
  was_edited_after_paste: false,
  delete_count: 0,
  revision_count: 0,
};

export type GrowthAnswersState = Record<GrowthQuestionId, { text: string; meta: GrowthAnswerMetaState }>;
