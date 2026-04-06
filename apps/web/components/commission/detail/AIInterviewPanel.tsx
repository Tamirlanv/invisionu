"use client";

import { useCallback, useEffect, useState } from "react";
import type { AiInterviewDraftQuestion, AiInterviewDraftView } from "@/lib/commission/types";
import { ApiError } from "@/lib/api-client";
import {
  approveAiInterview,
  generateAiInterviewDraft,
  getAiInterviewDraft,
  patchAiInterviewDraft,
} from "@/lib/commission/query";
import styles from "./ai-interview-panel.module.css";

type Props = {
  applicationId: string;
  canGenerate: boolean;
  canApprove: boolean;
  onChanged: () => Promise<void>;
  /** When false, panel is not shown and does not fetch (commission on another column/tab). */
  isActive?: boolean;
};

function displayText(q: AiInterviewDraftQuestion): string {
  return (q.commissionEditedText ?? q.questionText ?? "").trim();
}

function severityLabel(raw: string | undefined): string {
  if (!raw) return "—";
  const s = raw.toLowerCase();
  if (s === "high" || s === "высокий") return "высокая";
  if (s === "medium" || s === "средний") return "средняя";
  if (s === "low" || s === "низкий") return "низкая";
  return raw;
}

/** Подписи для reasonType — только если в данных нет reasonDescription (технические ключи в UI не показываем). */
const REASON_TYPE_LABEL_RU: Record<string, string> = {
  contradiction: "Уточнение по согласованности материалов заявки.",
  low_concreteness: "Необходимо больше конкретики в ответах.",
  authenticity_check: "Уточнение по достоверности и деталям формулировок.",
  missing_context: "Нужен дополнительный контекст по материалам.",
  strong_signal_clarification: "Необходимо уточнить конкретные примеры применения навыков.",
};

function reasonLine(q: AiInterviewDraftQuestion): string {
  const desc = (q.reasonDescription ?? "").trim();
  if (desc) return desc;
  const rt = (q.reasonType ?? "").trim().toLowerCase();
  if (rt && REASON_TYPE_LABEL_RU[rt]) return REASON_TYPE_LABEL_RU[rt];
  return "—";
}

export function AIInterviewPanel({
  applicationId,
  canGenerate,
  canApprove,
  onChanged,
  isActive = true,
}: Props) {
  const [draft, setDraft] = useState<AiInterviewDraftView | null>(null);
  const [loading, setLoading] = useState(true);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [edited, setEdited] = useState<AiInterviewDraftQuestion[] | null>(null);
  const [isHelpOpen, setIsHelpOpen] = useState(false);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const d = await getAiInterviewDraft(applicationId);
      setDraft(d);
      setEdited(d.questions.map((q) => ({ ...q })));
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) {
        setDraft(null);
        setEdited(null);
      } else {
        setError(e instanceof Error ? e.message : "Не удалось загрузить черновик");
      }
    } finally {
      setLoading(false);
    }
  }, [applicationId]);

  useEffect(() => {
    if (!isActive) return;
    void reload();
  }, [applicationId, isActive, reload]);

  async function withOp(fn: () => Promise<void>) {
    setPending(true);
    setError(null);
    try {
      await fn();
      await onChanged();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Ошибка");
    } finally {
      setPending(false);
    }
  }

  function updateQuestionText(index: number, text: string) {
    if (!edited) return;
    const next = edited.map((q, i) =>
      i === index ? { ...q, commissionEditedText: text, isEditedByCommission: true } : q,
    );
    setEdited(next);
  }

  async function saveDraft() {
    if (!draft || !edited) return;
    setPending(true);
    setError(null);
    try {
      await patchAiInterviewDraft(applicationId, {
        revision: draft.revision,
        questions: edited as Record<string, unknown>[],
      });
      await onChanged();
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Не удалось сохранить");
    } finally {
      setPending(false);
    }
  }

  async function handleGenerate() {
    const force = Boolean(draft?.status === "draft");
    if (force && !window.confirm("Перегенерировать вопросы? Текущий черновик и правки будут заменены.")) {
      return;
    }
    await withOp(async () => {
      await generateAiInterviewDraft(applicationId, force);
    });
  }

  const validCount = edited?.filter((q) => displayText(q)).length ?? 0;
  const isDraft = draft?.status === "draft";
  const generationSource = (draft?.generationSource ?? "").toLowerCase();
  const sourceLabel = generationSource === "llm" ? "LLM" : generationSource ? "Контекстный fallback" : null;
  const fallbackHint =
    sourceLabel === "Контекстный fallback"
      ? "Черновик собран резервным способом на основе сигналов заявки."
      : null;

  if (!isActive) return null;

  return (
    <section style={{ display: "grid", gap: 12, minWidth: 0 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap" }}>
        <h3 style={{ margin: 0, fontSize: 20, fontWeight: 550, color: "#262626", letterSpacing: "-0.6px", lineHeight: "20px" }}>
          Вопросы для AI-собеседования
        </h3>
        <button
          type="button"
          onClick={() => setIsHelpOpen(true)}
          style={{
            margin: 0,
            padding: 0,
            border: "none",
            background: "none",
            cursor: "pointer",
            fontSize: 14,
            fontWeight: 350,
            color: "#626262",
            letterSpacing: "-0.42px",
            lineHeight: "14px",
            textDecoration: "underline",
            fontFamily: "inherit",
          }}
        >
          Как это работает?
        </button>
      </div>
      <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px", whiteSpace: "pre-wrap" }}>
        Сгенерируйте 3–5 вопросов по материалам заявки, отредактируйте формулировки и одобрите набор. После одобрения кандидат переходит на этап «Собеседование» и видит только текст вопросов.
      </p>

      {error ? <p style={{ margin: 0, color: "#c62828", fontSize: 14 }}>{error}</p> : null}

      {loading ? (
        <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>Загрузка…</p>
      ) : (
        <>
          {!draft && !loading ? (
            <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>
              Черновик ещё не создан. Нажмите «Перегенерировать», чтобы собрать вопросы.
            </p>
          ) : null}
          {draft && draft.status === "approved" ? (
            <p style={{ margin: 0, fontSize: 14, color: "#2e7d32" }}>Набор одобрён.</p>
          ) : null}
          {draft && sourceLabel ? (
            <p style={{ margin: 0, fontSize: 13, color: "#626262" }}>
              Источник: {sourceLabel}
              {typeof draft.issueCount === "number" ? ` · Сигналов к уточнению: ${draft.issueCount}` : ""}
              {fallbackHint ? ` · ${fallbackHint}` : ""}
            </p>
          ) : null}

          {edited && edited.length > 0 ? (
            <div style={{ display: "grid", gap: 24 }}>
              {edited.map((q, i) => (
                <div key={q.id || i}>
                  <div style={{ display: "grid", gap: 8 }}>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                      Вопрос {i + 1}
                    </p>
                    {canGenerate && isDraft ? (
                      <textarea
                        className={styles.textarea}
                        rows={4}
                        value={displayText(q) || q.questionText}
                        onChange={(e) => updateQuestionText(i, e.target.value)}
                      />
                    ) : (
                      <div className={styles.readonlyBox}>{displayText(q) || q.questionText}</div>
                    )}
                    <div
                      style={{
                        display: "flex",
                        justifyContent: "space-between",
                        alignItems: "center",
                        gap: 12,
                        flexWrap: "wrap",
                        fontSize: 14,
                        fontWeight: 350,
                        color: "#626262",
                        letterSpacing: "-0.42px",
                        lineHeight: "14px",
                      }}
                    >
                      <span style={{ flex: "1 1 auto", minWidth: 0 }}>{reasonLine(q)}</span>
                      <span style={{ whiteSpace: "nowrap" }}>Важность: {severityLabel(q.severity)}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : null}

          {edited && isDraft ? (
            <p style={{ margin: 0, fontSize: 13, color: "#626262" }}>
              Вопросов с текстом: {validCount} (нужно 3–5 для одобрения). Ревизия черновика: {draft?.revision ?? "—"}.
            </p>
          ) : null}

          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center" }}>
            {canGenerate ? (
              <button type="button" className="btn secondary" disabled={pending} onClick={() => void handleGenerate()}>
                Перегенерировать
              </button>
            ) : null}
            {canGenerate && edited && isDraft ? (
              <button type="button" className="btn secondary" disabled={pending} onClick={() => void withOp(saveDraft)}>
                Сохранить черновик
              </button>
            ) : null}
            {canApprove && isDraft ? (
              <button
                type="button"
                className="btn"
                disabled={pending || validCount < 3 || validCount > 5}
                onClick={() =>
                  void withOp(async () => {
                    await approveAiInterview(applicationId);
                  })
                }
              >
                Одобрить
              </button>
            ) : null}
          </div>
        </>
      )}

      <AiInterviewHowItWorksModal open={isHelpOpen} onClose={() => setIsHelpOpen(false)} />
    </section>
  );
}

type AiInterviewHowItWorksModalProps = {
  open: boolean;
  onClose: () => void;
};

function AiInterviewHowItWorksModal({ open, onClose }: AiInterviewHowItWorksModalProps) {
  useEffect(() => {
    if (!open) return;
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="ai-interview-how-it-works-title"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 1200,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.45)",
        padding: 16,
      }}
      onMouseDown={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: "min(560px, 100%)",
          background: "#fff",
          borderRadius: 16,
          padding: "24px 20px",
          boxShadow: "0 8px 32px rgba(0,0,0,0.2)",
        }}
      >
        <h2 id="ai-interview-how-it-works-title" style={{ margin: "0 0 12px", fontSize: 18, fontWeight: 600 }}>
          Как формируются вопросы
        </h2>
        <p style={{ margin: 0, fontSize: 14, lineHeight: 1.5, color: "#262626" }}>
          Вопросы собираются из анкеты кандидата и материалов заявки. Они помогают комиссии точечно уточнить слабые
          или спорные места, закрыть противоречия и добрать недостающие детали. Поэтому у разных кандидатов набор
          вопросов отличается и зависит от того, что именно осталось не до конца раскрыто.
        </p>
        <div style={{ marginTop: 20, display: "flex", justifyContent: "center" }}>
          <button type="button" className="btn" style={{ width: "fit-content" }} onClick={onClose}>
            Понятно
          </button>
        </div>
      </div>
    </div>
  );
}
