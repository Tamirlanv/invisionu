"use client";

import { useCallback, useEffect, useState } from "react";
import { ApiError } from "@/lib/api-client";
import { resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import { getCommissionAiInterviewCandidateSession, postCommissionInterviewOutcome } from "@/lib/commission/query";
import type { CommissionAiInterviewSessionView } from "@/lib/commission/types";
import { formatPreferenceVariantLine } from "@/lib/commission/interviewScheduleOptions";
import { CommissionInterviewScheduleBlock } from "@/components/commission/detail/CommissionInterviewScheduleBlock";
import styles from "./CommissionInterviewWithCommissionPanel.module.css";

type Props = {
  applicationId: string;
  isActive: boolean;
  readOnly?: boolean;
  candidateFullName?: string | null;
};

function padVariants(
  slots: CommissionAiInterviewSessionView["preferredSlots"],
): Array<{ date: string; timeRangeCode: string; timeRange: string } | null> {
  const out: Array<{ date: string; timeRangeCode: string; timeRange: string } | null> = [...slots];
  while (out.length < 3) out.push(null);
  return out.slice(0, 3);
}

function formatDateTime(raw: string, candidateFullName: string | null | undefined): string {
  const dt = resolveDisplayDate(raw, candidateFullName);
  if (!dt) return raw;
  return dt.toLocaleString("ru-RU");
}

export function CommissionInterviewWithCommissionPanel({
  applicationId,
  isActive,
  readOnly = false,
  candidateFullName,
}: Props) {
  const [data, setData] = useState<CommissionAiInterviewSessionView | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [prefillSlot, setPrefillSlot] = useState<{ date: string; timeRangeCode: string } | null>(null);
  const [prefillVersion, setPrefillVersion] = useState(0);
  const [outcomePending, setOutcomePending] = useState(false);
  const [outcomeError, setOutcomeError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await getCommissionAiInterviewCandidateSession(applicationId);
      setData(d);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setData(null);
      } else {
        setError(e instanceof Error ? e.message : "Не удалось загрузить данные");
        setData(null);
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    if (!isActive) return;
    void load();
  }, [isActive, load]);

  useEffect(() => {
    if (!isActive) return;
    const id = setInterval(() => void load(), 60_000);
    return () => clearInterval(id);
  }, [isActive, load]);

  if (!isActive) return null;

  const regularWeight = 350 as const;

  if (loading) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#626262" }}>Загрузка…</p>;
  }

  if (error) {
    return <p style={{ margin: 0, fontSize: 14, fontWeight: regularWeight, color: "#c62828" }}>{error}</p>;
  }

  if (!data?.interviewCompletedAt) {
    return (
      <p style={{ margin: 0, fontSize: 14, lineHeight: 1.4, fontWeight: regularWeight, color: "#626262" }}>
        Кандидат ещё не завершил AI-собеседование. После завершения здесь появятся удобное время кандидата и
        назначение собеседования с комиссией.
      </p>
    );
  }

  const cp =
    data.candidatePreferencePanel ?? {
      preferredSlots: data.preferredSlots ?? [],
      preferencesSubmittedAt: null,
      windowStatus: null,
      windowOpenedAt: null,
      windowExpiresAt: null,
      remainingSeconds: null,
    };

  const scheduledInterview = data.commissionSchedule?.scheduledInterview ?? null;
  const hasSlots = cp.preferredSlots.length > 0;
  const variants = padVariants(cp.preferredSlots);

  const onPickVariant = (slot: { date: string; timeRangeCode: string; timeRange: string } | null) => {
    if (!slot?.date?.trim() || !slot.timeRangeCode?.trim()) return;
    setPrefillSlot({ date: slot.date, timeRangeCode: slot.timeRangeCode });
    setPrefillVersion((v) => v + 1);
  };

  return (
    <div style={{ display: "grid", gap: 0, fontSize: 14 }}>
      <section className={styles.section} aria-labelledby="commission-preferred-time-heading">
        <h3 id="commission-preferred-time-heading" className={styles.title}>
          Желаемое время
        </h3>
        <p className={styles.lead}>
          Здесь будет указано, в какое время кандидату удобно пройти собеседование
        </p>

        {hasSlots ? (
          <div className={styles.variants}>
            {variants.map((slot, i) => {
              const line = slot
                ? formatPreferenceVariantLine(slot.date, slot.timeRange)
                : "—";
              const canClick = Boolean(slot?.date && slot?.timeRangeCode);
              return (
                <div key={`v-${i}`} className={styles.variantRow}>
                  <span className={styles.variantLabel}>Вариант {i + 1}:</span>
                  {canClick ? (
                    <button
                      type="button"
                      className={styles.variantValue}
                      onClick={() => onPickVariant(slot)}
                    >
                      {line}
                    </button>
                  ) : (
                    <span className={styles.variantValueMuted}>{line}</span>
                  )}
                </div>
              );
            })}
            {cp.preferencesSubmittedAt ? (
              <p className={styles.meta}>
                Отправлено: {formatDateTime(cp.preferencesSubmittedAt, candidateFullName)}
              </p>
            ) : null}
          </div>
        ) : null}

        {!hasSlots && cp.windowStatus === "awaiting_candidate_preferences" ? (
          <p className={styles.wait}>
            Кандидат еще не выбрал желаемое время собеседования, ожидайте: 1 час
            {cp.remainingSeconds != null && cp.remainingSeconds > 0 ? (
              <>
                {" "}
                (осталось ~{Math.max(1, Math.ceil(cp.remainingSeconds / 60))} мин.)
              </>
            ) : null}
          </p>
        ) : null}

        {!hasSlots && cp.windowStatus === "candidate_preferences_expired" ? (
          <p className={styles.wait}>
            Кандидат не выбрал желаемое время в отведённый срок. Комиссия может назначить собеседование
            самостоятельно.
          </p>
        ) : null}

        {!hasSlots &&
        cp.windowStatus !== "awaiting_candidate_preferences" &&
        cp.windowStatus !== "candidate_preferences_expired" ? (
          <p className={styles.wait}>Пока нет выбранных слотов.</p>
        ) : null}
      </section>

      <CommissionInterviewScheduleBlock
        applicationId={applicationId}
        initial={scheduledInterview}
        onSaved={() => void load()}
        prefillSlot={prefillSlot}
        prefillVersion={prefillVersion}
        readOnly={readOnly}
        candidateFullName={candidateFullName}
      />

      {scheduledInterview?.scheduledAt && !scheduledInterview.outcomeRecordedAt ? (
        <section className={styles.section} style={{ marginTop: 16 }} aria-labelledby="commission-outcome-heading">
          <h3 id="commission-outcome-heading" className={styles.title}>
            Итог собеседования
          </h3>
          <p className={styles.lead}>
            После проведения собеседования зафиксируйте итог — это требуется для перевода заявки на этап «Решение
            комиссии» на доске.
          </p>
          <button
            type="button"
            className="btn"
            disabled={outcomePending || readOnly}
            onClick={() => {
              if (readOnly) return;
              setOutcomePending(true);
              setOutcomeError(null);
              void (async () => {
                try {
                  await postCommissionInterviewOutcome(applicationId);
                  await load();
                } catch (e) {
                  setOutcomeError(e instanceof Error ? e.message : "Не удалось сохранить");
                } finally {
                  setOutcomePending(false);
                }
              })();
            }}
          >
            {outcomePending ? "Сохранение…" : "Подтвердить итог собеседования"}
          </button>
          {readOnly ? (
            <p style={{ margin: "8px 0 0", fontSize: 13, color: "#626262" }}>
              Для этой заявки включен режим только просмотра.
            </p>
          ) : null}
          {outcomeError ? (
            <p style={{ margin: "8px 0 0", fontSize: 14, color: "#c62828" }}>{outcomeError}</p>
          ) : null}
        </section>
      ) : null}

      {scheduledInterview?.outcomeRecordedAt ? (
        <p className={styles.meta} style={{ marginTop: 16 }}>
          Итог собеседования зафиксирован:{" "}
          {formatDateTime(scheduledInterview.outcomeRecordedAt, candidateFullName)}
        </p>
      ) : null}
    </div>
  );
}
