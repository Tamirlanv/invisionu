export type SubmitOutcomeSummary = {
  queue_status?: string;
  queue_message?: string | null;
};

export function getSubmitSuccessMessage(submitOutcome?: SubmitOutcomeSummary): string {
  if (submitOutcome?.queue_status === "degraded") {
    return submitOutcome.queue_message ?? "Анкета отправлена. Часть фоновой обработки ожидает восстановления сервиса.";
  }
  return "Анкета успешно отправлена.";
}
