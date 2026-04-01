import type { CommissionRange, CommissionStage } from "./types";

export const COMMISSION_STAGE_ORDER: CommissionStage[] = [
  "data_check",
  "application_review",
  "interview",
  "committee_decision",
  "result",
];

export const COMMISSION_STAGE_TITLES: Record<CommissionStage, string> = {
  data_check: "Проверка данных",
  application_review: "Оценка заявки",
  interview: "Собеседование",
  committee_decision: "Решение комиссии",
  result: "Результат",
};

export const COMMISSION_RANGE_OPTIONS: { value: CommissionRange; label: string }[] = [
  { value: "day", label: "День" },
  { value: "week", label: "Неделя" },
  { value: "month", label: "Месяц" },
  { value: "year", label: "Год" },
];

