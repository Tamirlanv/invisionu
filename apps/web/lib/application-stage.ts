export const CANDIDATE_STAGE_PIPELINE = [
  { stage: "application", label: "Подача анкеты" },
  { stage: "initial_screening", label: "Проверка данных" },
  { stage: "application_review", label: "Оценка заявки" },
  { stage: "interview", label: "Собеседование" },
  { stage: "committee_review", label: "Решение комиссии" },
  { stage: "decision", label: "Результат" },
] as const;

export function getCandidateStageIndex(stage: string | null | undefined): number {
  if (!stage) return 0;
  const idx = CANDIDATE_STAGE_PIPELINE.findIndex((item) => item.stage === stage);
  return idx >= 0 ? idx : 0;
}
