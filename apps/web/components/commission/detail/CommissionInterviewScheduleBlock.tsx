"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import { postCommissionInterviewSchedule } from "@/lib/commission/query";
import type { CommissionScheduledInterviewPayload } from "@/lib/commission/types";
import {
  buildScheduleDayOptions,
  COMMISSION_TIME_SLOT_OPTIONS,
  dateAndCodeToDatetimeLocal,
  mergeScheduleDayOptions,
  timeOptionsIncludingCode,
} from "@/lib/commission/interviewScheduleOptions";
import styles from "./CommissionInterviewScheduleBlock.module.css";

type Props = {
  applicationId: string;
  initial: CommissionScheduledInterviewPayload | null;
  onSaved: () => void;
  readOnly?: boolean;
  candidateFullName?: string | null;
  /** Click candidate variant — fill date/time in this form */
  prefillSlot?: { date: string; timeRangeCode: string } | null;
  /** Bump to re-apply the same slot */
  prefillVersion?: number;
};

export function CommissionInterviewScheduleBlock({
  applicationId,
  initial,
  onSaved,
  readOnly = false,
  candidateFullName,
  prefillSlot,
  prefillVersion = 0,
}: Props) {
  const baseDayOptions = useMemo(() => buildScheduleDayOptions(), []);
  const [dateStr, setDateStr] = useState("");
  const [timeCode, setTimeCode] = useState("");
  const [locationOrLink, setLocationOrLink] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  /** True until parent refetches and `initial.scheduledAt` is set (avoids flash after POST). */
  const [localScheduleSuccess, setLocalScheduleSuccess] = useState(false);

  const isScheduled = Boolean(initial?.scheduledAt) || localScheduleSuccess;

  useEffect(() => {
    if (initial?.scheduledAt) {
      setLocalScheduleSuccess(false);
    }
  }, [initial?.scheduledAt]);

  useEffect(() => {
    if (initial?.scheduledAt) {
      const d = new Date(initial.scheduledAt);
      const pad = (n: number) => n.toString().padStart(2, "0");
      const y = d.getFullYear();
      const m = pad(d.getMonth() + 1);
      const day = pad(d.getDate());
      setDateStr(`${y}-${m}-${day}`);
      const hour = d.getHours();
      const codeFromHour = `${pad(hour)}-${pad(hour + 1)}`;
      const match = COMMISSION_TIME_SLOT_OPTIONS.find((o) => o.value === codeFromHour);
      setTimeCode(match?.value ?? COMMISSION_TIME_SLOT_OPTIONS[0]?.value ?? "");
      setLocationOrLink(initial.locationOrLink ?? "");
    } else {
      setDateStr("");
      setTimeCode("");
      setLocationOrLink("");
    }
  }, [initial]);

  const scheduledDateIso = initial?.scheduledAt
    ? (() => {
        const d = new Date(initial.scheduledAt);
        const pad = (n: number) => n.toString().padStart(2, "0");
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
      })()
    : undefined;

  const dayOptions = useMemo(() => {
    let opts = baseDayOptions;
    opts = mergeScheduleDayOptions(opts, scheduledDateIso);
    opts = mergeScheduleDayOptions(opts, prefillSlot?.date);
    opts = mergeScheduleDayOptions(opts, dateStr);
    return opts;
  }, [baseDayOptions, scheduledDateIso, prefillSlot?.date, dateStr]);

  useEffect(() => {
    if (isScheduled) return;
    if (!prefillSlot?.date || !prefillSlot.timeRangeCode) return;
    setDateStr(prefillSlot.date);
    setTimeCode(prefillSlot.timeRangeCode);
    setError(null);
  }, [prefillSlot, prefillVersion, isScheduled]);

  const timeOptions = timeOptionsIncludingCode(timeCode);

  const linkTrimmed = locationOrLink.trim();
  const formComplete = Boolean(dateStr.trim() && timeCode.trim() && linkTrimmed);

  const submit = useCallback(async () => {
    if (readOnly) return;
    const link = locationOrLink.trim();
    if (!dateStr.trim() || !timeCode.trim()) {
      setError("Укажите дату и время");
      return;
    }
    if (!link) {
      setError("Укажите ссылку на платформу");
      return;
    }
    setPending(true);
    setError(null);
    try {
      const localStr = dateAndCodeToDatetimeLocal(dateStr, timeCode);
      const scheduledAt = new Date(localStr);
      if (Number.isNaN(scheduledAt.getTime())) {
        setError("Некорректная дата или время");
        return;
      }
      await postCommissionInterviewSchedule(applicationId, {
        scheduledAt: scheduledAt.toISOString(),
        interviewMode: null,
        locationOrLink: link,
      });
      setLocalScheduleSuccess(true);
      onSaved();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setPending(false);
    }
  }, [applicationId, dateStr, timeCode, locationOrLink, onSaved, readOnly]);

  return (
    <div className={styles.wrap}>
      <h4 className={styles.title}>Назначить время</h4>
      {readOnly ? (
        <p className={styles.currentNote}>Режим только просмотра: назначение недоступно.</p>
      ) : null}

      {initial?.scheduledAt ? (
        <p className={styles.currentNote}>
          Текущее назначение:{" "}
          {(resolveDisplayDate(initial.scheduledAt, candidateFullName) ?? new Date(initial.scheduledAt)).toLocaleString(
            "ru-RU",
            { dateStyle: "long", timeStyle: "short" },
          )}
          {initial.interviewMode ? ` · ${initial.interviewMode}` : ""}
        </p>
      ) : null}

      <div className={styles.row}>
        <select
          className={styles.select}
          aria-label="Дата собеседования"
          value={dateStr}
          disabled={pending || isScheduled || readOnly}
          onChange={(e) => setDateStr(e.target.value)}
        >
          <option value="">День</option>
          {dayOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
        <select
          className={styles.select}
          aria-label="Интервал времени"
          value={timeCode}
          disabled={pending || isScheduled || readOnly}
          onChange={(e) => setTimeCode(e.target.value)}
        >
          <option value="">Время</option>
          {timeOptions.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>

      <label className={styles.linkLabel}>
        Ссылка на платформу
        <input
          type="text"
          className={styles.linkInput}
          value={locationOrLink}
          disabled={pending || isScheduled || readOnly}
          onChange={(e) => setLocationOrLink(e.target.value)}
          placeholder="Вставьте ссылку"
          autoComplete="off"
        />
      </label>

      {error ? <p className={styles.error}>{error}</p> : null}

      <button
        type="button"
        className={`${styles.submit} ${isScheduled && !pending ? styles.submitScheduled : ""}`}
        disabled={isScheduled || pending || !formComplete || readOnly}
        onClick={() => void submit()}
      >
        {pending ? "Сохранение…" : isScheduled ? "Собеседование назначено" : "Назначить"}
      </button>
    </div>
  );
}
