"use client";

import { useEffect, useState } from "react";
import { ApiError, apiFetchCached } from "@/lib/api-client";
import { CANDIDATE_STAGE_PIPELINE, getCandidateStageIndex } from "@/lib/application-stage";
import type { CandidateApplicationStatus } from "@/lib/candidate-status";
import { CAMPAIGN_DURATION_MS, getAdmissionDeadlineMs } from "@/lib/deadline";
import styles from "./application-sidebar.module.css";

const DOC_CHECKLIST = [
  "Паспорт/ID",
  "Презентация",
  "Результаты теста на знание английского языка",
  "Результаты ЕНТ/Сертификат 12 классов NIS",
];

const STATUS_TTL_MS = 2 * 60 * 1000;

type Props = {
  statusData?: CandidateApplicationStatus | null;
  statusError?: string | null;
  statusLoading?: boolean;
};

function StepDot({ active }: { active: boolean }) {
  return (
    <svg
      className={styles.stepDot}
      width={14}
      height={14}
      viewBox="0 0 14 14"
      fill="none"
      aria-hidden
    >
      <circle cx="7" cy="7" r="7" fill={active ? "#98DA00" : "#E1E1E1"} />
    </svg>
  );
}

/** Радиус кольца в viewBox 56×56, stroke 6 — как в макете */
const R = 24;
const STROKE = 6;
const CIRC = 2 * Math.PI * R;

function useDeadlineCountdown() {
  const [parts, setParts] = useState({ d: 0, h: 0, m: 0 });
  const [ringRatio, setRingRatio] = useState(1);

  useEffect(() => {
    const end = getAdmissionDeadlineMs();
    const tick = () => {
      const now = Date.now();
      const diff = Math.max(0, end - now);
      const d = Math.floor(diff / (24 * 60 * 60 * 1000));
      const h = Math.floor((diff % (24 * 60 * 60 * 1000)) / (60 * 60 * 1000));
      const m = Math.floor((diff % (60 * 60 * 1000)) / (60 * 1000));
      setParts({ d, h, m });
      const remainingRatio = Math.min(1, Math.max(0, diff / CAMPAIGN_DURATION_MS));
      setRingRatio(Number.isFinite(remainingRatio) ? remainingRatio : 0);
    };
    tick();
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  return { parts, ringRatio };
}

export function ApplicationSidebar({ statusData, statusError: externalStatusError, statusLoading = false }: Props) {
  const { parts, ringRatio } = useDeadlineCountdown();
  const [status, setStatus] = useState<CandidateApplicationStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    if (statusData !== undefined) {
      setStatus(statusData);
      setStatusError(externalStatusError ?? null);
      return;
    }
    let cancelled = false;
    async function loadStatus() {
      try {
        const data = await apiFetchCached<CandidateApplicationStatus>("/candidates/me/application/status", STATUS_TTL_MS);
        if (cancelled) return;
        setStatus(data);
        setStatusError(null);
      } catch (error) {
        if (cancelled) return;
        setStatusError(error instanceof ApiError ? error.message : "Не удалось загрузить статус этапа.");
      }
    }
    void loadStatus();
    return () => {
      cancelled = true;
    };
  }, [statusData, externalStatusError]);

  const offset = CIRC * (1 - ringRatio);
  const activeStepIndex = getCandidateStageIndex(status?.current_stage);
  const stageItems = CANDIDATE_STAGE_PIPELINE.map((item, idx) => ({
    ...item,
    reached: idx <= activeStepIndex,
  }));

  return (
    <aside className={styles.sidebar}>
      <div className={styles.deadlineCard}>
        <div className={styles.deadlineLeft}>
          <h3 className={styles.deadlineTitle}>Срок подачи заявки</h3>
          <div className={styles.timerRow}>
            <img
              src="/assets/icons/ic_round-timer.svg"
              alt=""
              width={24}
              height={24}
              className={styles.timerIcon}
            />
            <div className={styles.timerDigits}>
              <span>{parts.d} д</span>
              <span>{parts.h} ч</span>
              <span>{parts.m} м</span>
            </div>
          </div>
        </div>
        <div className={styles.circularWrap} aria-hidden>
          <svg width="56" height="56" viewBox="0 0 56 56">
            <circle cx="28" cy="28" r={R} fill="none" stroke="#f1f1f1" strokeWidth={STROKE} />
            <circle
              cx="28"
              cy="28"
              r={R}
              fill="none"
              stroke="#98da00"
              strokeWidth={STROKE}
              strokeLinecap="round"
              strokeDasharray={CIRC}
              strokeDashoffset={offset}
              transform="rotate(-90 28 28)"
              className={styles.progressArc}
            />
          </svg>
        </div>
      </div>

      <div className={styles.stepsCard}>
        <div className={styles.stepsListContainer}>
          {/* Title row: "Этап X/6" */}
          <div className={styles.stepsTitleRow}>
            <p className={styles.stepsTitleText}>Этап</p>
            <p className={styles.stepsTitleText}>
              {statusLoading && !status ? "—" : `${activeStepIndex + 1}/${CANDIDATE_STAGE_PIPELINE.length}`}
            </p>
          </div>

          {/* Stage list */}
          <div className={styles.stepList}>
            {stageItems.map((step, idx) => (
              <div key={step.stage}>
                <div className={styles.stepItem}>
                  <StepDot active={step.reached} />
                  <p className={step.reached ? styles.labelActive : styles.labelInactive}>{step.label}</p>
                </div>
                {/* Dotted connector after current active stage */}
                {idx === activeStepIndex && idx < stageItems.length - 1 ? (
                  <div className={styles.stageConnector} aria-hidden>
                    <svg width="4" height="20" viewBox="0 0 4 20" fill="none">
                      <path
                        d="M2 2V18"
                        stroke="#98DA00"
                        strokeWidth="4"
                        strokeLinecap="round"
                        strokeDasharray="0.1 8"
                      />
                    </svg>
                  </div>
                ) : null}
              </div>
            ))}
          </div>
        </div>
      </div>

      <div className={styles.card}>
        <h3 className={styles.cardTitle}>Документы</h3>
        <div className={styles.documentsList}>
          {DOC_CHECKLIST.map((t) => (
            <div key={t} className={styles.docItem}>
              {t}
            </div>
          ))}
        </div>
      </div>
    </aside>
  );
}
