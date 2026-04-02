"use client";

import Image from "next/image";
import { useCallback, useEffect, useRef, useState } from "react";
import { type ApplicationCompletionSummary } from "@/lib/application-completion";
import { formatFileSize } from "@/lib/file-upload";
import { getSubmitSuccessMessage } from "@/lib/submit-outcome";
import styles from "./submit-modal.module.css";

export type ModalDocument = {
  id: string;
  document_type: string;
  original_filename: string;
  byte_size: number;
};

type Props = {
  open: boolean;
  onClose: () => void;
  onConfirm: () => Promise<{
    submit_outcome?: {
      queue_status?: string;
      queue_message?: string | null;
    };
  }>;
  completionSummary: ApplicationCompletionSummary;
  reviewLoading: boolean;
  reviewError: string | null;
  onRetryReview: () => void;
  documents: ModalDocument[];
};

export function SubmitConfirmationModal({
  open,
  onClose,
  onConfirm,
  completionSummary,
  reviewLoading,
  reviewError,
  onRetryReview,
  documents,
}: Props) {
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; msg: string } | null>(null);
  const overlayRef = useRef<HTMLDivElement>(null);

  const canSubmit = completionSummary.canSubmit && !submitting && !reviewLoading;
  const completeSections = completionSummary.sections.filter((s) => s.status === "complete");
  const incompleteSections = completionSummary.sections.filter((s) => s.status === "incomplete");
  const emptySections = completionSummary.sections.filter((s) => s.status === "empty");

  const handleConfirm = useCallback(async () => {
    setSubmitting(true);
    setResult(null);
    try {
      const submitResponse = await onConfirm();
      setResult({
        ok: true,
        msg: getSubmitSuccessMessage(submitResponse.submit_outcome),
      });
    } catch (e) {
      setResult({
        ok: false,
        msg: e instanceof Error ? e.message : "Не удалось отправить",
      });
    } finally {
      setSubmitting(false);
    }
  }, [onConfirm]);

  useEffect(() => {
    if (!open) {
      setResult(null);
      setSubmitting(false);
    }
  }, [open]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape" && open && !submitting) onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, submitting, onClose]);

  if (!open) return null;

  return (
    <div
      ref={overlayRef}
      className={styles.overlay}
      onClick={(e) => {
        if (e.target === overlayRef.current && !submitting) onClose();
      }}
    >
      <div className={styles.modal} role="dialog" aria-modal="true">
        <div className={styles.header}>
          <div>
            <p className={styles.title}>Отправка анкеты</p>
            <p className={styles.subtitle}>Проверьте корректность ваших данных</p>
          </div>
          <p className={styles.completionText}>
            {reviewLoading ? "Обновляем статус..." : `Заполнено ${completionSummary.percent}%`}
          </p>
        </div>

        <div className={styles.body}>
          <div className={styles.sectionsColumn}>
            {reviewLoading ? (
              <div className={styles.sectionGroup}>
                <p className={styles.sectionItem}>Загружаем актуальное состояние анкеты...</p>
              </div>
            ) : (
              <>
                {emptySections.length > 0 && (
                  <div className={styles.sectionGroup}>
                    <p className={styles.sectionGroupTitle}>Пусто</p>
                    {emptySections.map((section) => (
                      <p key={section.sectionKey} className={styles.sectionItem}>
                        {section.title}
                      </p>
                    ))}
                  </div>
                )}
                {incompleteSections.length > 0 && (
                  <div className={styles.sectionGroup}>
                    <p className={styles.sectionGroupTitle}>Неполно</p>
                    {incompleteSections.map((section) => (
                      <p key={section.sectionKey} className={styles.sectionItem}>
                        {section.title}
                      </p>
                    ))}
                  </div>
                )}
                {completeSections.length > 0 && (
                  <div className={styles.sectionGroup}>
                    <p className={styles.sectionGroupTitle}>Готово</p>
                    {completeSections.map((section) => (
                      <p key={section.sectionKey} className={styles.sectionItem}>
                        {section.title}
                      </p>
                    ))}
                  </div>
                )}
              </>
            )}
          </div>

          <div className={styles.docsColumn}>
            <p className={styles.docsTitle}>Документы</p>
            {documents.length === 0 ? (
              <p className={styles.noDocsText}>Нет загруженных документов</p>
            ) : (
              <div className={styles.docsList}>
                {documents.map((d) => (
                  <div key={d.id} className={styles.docCard}>
                    <Image
                      className={styles.docIcon}
                      src="/assets/icons/solar_file-bold.svg"
                      alt=""
                      width={36}
                      height={36}
                      unoptimized
                    />
                    <div className={styles.docInfo}>
                      <p className={styles.docName}>{d.original_filename}</p>
                      <p className={styles.docSize}>{formatFileSize(d.byte_size)}</p>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {result && (
          <p className={result.ok ? styles.successMsg : styles.errorMsg}>
            {result.msg}
          </p>
        )}
        {!result && reviewError && (
          <p className={styles.errorMsg}>
            {reviewError}{" "}
            <button type="button" onClick={onRetryReview}>
              Повторить
            </button>
          </p>
        )}

        {result?.ok ? (
          <button className={styles.submitBtn} type="button" onClick={onClose}>
            Закрыть
          </button>
        ) : (
          <button
            className={styles.submitBtn}
            type="button"
            disabled={!canSubmit}
            onClick={() => void handleConfirm()}
          >
            {submitting
              ? "Отправка..."
              : reviewLoading
                ? "Обновляем статус..."
                : completionSummary.locked
                ? "Уже отправлено"
                : "Отправить анкету"}
          </button>
        )}
      </div>
    </div>
  );
}
