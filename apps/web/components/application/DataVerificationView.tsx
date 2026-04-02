"use client";

import { useState } from "react";
import type { CandidateApplicationStatus } from "@/lib/candidate-status";
import { FALLBACK_CENTER_BODY, FALLBACK_ETA, buildDataVerificationCopy } from "@/lib/data-verification-copy";
import styles from "./data-verification-view.module.css";

type Props = {
  status: CandidateApplicationStatus | null;
  onRetrySubmit?: () => Promise<void>;
};

export function DataVerificationView({ status, onRetrySubmit }: Props) {
  const { centerBody, queueWarning } = buildDataVerificationCopy(status);
  const useFallbackBody = centerBody.trim() === FALLBACK_CENTER_BODY;
  const [retrying, setRetrying] = useState(false);
  const [retryError, setRetryError] = useState<string | null>(null);

  const canShowRetryButton = Boolean(queueWarning && onRetrySubmit);

  async function handleRetryClick() {
    if (!onRetrySubmit) return;
    setRetryError(null);
    setRetrying(true);
    try {
      await onRetrySubmit();
    } catch (error) {
      setRetryError(error instanceof Error ? error.message : "Не удалось вернуть анкету на этап заполнения.");
    } finally {
      setRetrying(false);
    }
  }

  return (
    <section className={styles.root}>
      <div className={styles.stageBlock}>
        <h2 className={styles.stageTitle}>Проверка данных</h2>
        <div className={styles.stageChipShell}>
          <div className={styles.stageChip}>Модерация</div>
        </div>
      </div>

      <div className={styles.centerBlock}>
        <h3 className={styles.centerTitle}>Ваша анкета на модерации</h3>
        {useFallbackBody ? (
          <div className={styles.centerTextFallback}>
            <p className={styles.centerText}>Пожалуйста ожидайте, ваши данные сейчас на этапе проверки модерации.</p>
            <p className={styles.centerText}>
              По окончании проверки на{" "}
              <span className={styles.centerTextEmphasis}>вашу почту придет сообщение о статусе заявки</span>
            </p>
          </div>
        ) : (
          <p className={styles.centerText}>{centerBody}</p>
        )}
        <p className={styles.etaText}>{FALLBACK_ETA}</p>
        {queueWarning ? <p className={styles.queueWarning}>{queueWarning}</p> : null}
        {canShowRetryButton ? (
          <button
            type="button"
            className={styles.retryButton}
            onClick={() => void handleRetryClick()}
            disabled={retrying}
          >
            {retrying ? "Возвращаем на первый этап..." : "Переотправить анкету"}
          </button>
        ) : null}
        {retryError ? <p className={styles.retryError}>{retryError}</p> : null}
      </div>
    </section>
  );
}
