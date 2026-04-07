"use client";

import { useState, useTransition } from "react";
import { createCommissionComment } from "@/lib/commission/query";
import { resolveDisplayDate } from "@/lib/commission/candidate-timestamp-override";
import type { CommissionApplicationPersonalInfoView } from "@/lib/commission/types";

const MONTHS_GEN = [
  "января",
  "февраля",
  "марта",
  "апреля",
  "мая",
  "июня",
  "июля",
  "августа",
  "сентября",
  "октября",
  "ноября",
  "декабря",
] as const;

function pad2(n: number): string {
  return String(n).padStart(2, "0");
}

/** Локальное время: сегодня 01:32 · вчера · 3 апреля · 27 марта 2025 */
function formatCommentTimestamp(iso: string | null, candidateFullName: string | null): string {
  if (!iso) return "—";
  const d = resolveDisplayDate(iso, candidateFullName);
  if (!d) return iso;

  const now = new Date();
  const startToday = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const startComment = new Date(d.getFullYear(), d.getMonth(), d.getDate());
  const diffDays = Math.round((startToday.getTime() - startComment.getTime()) / (24 * 60 * 60 * 1000));

  if (diffDays === 0) {
    return `сегодня ${pad2(d.getHours())}:${pad2(d.getMinutes())}`;
  }
  if (diffDays === 1) {
    return "вчера";
  }

  const day = d.getDate();
  const month = MONTHS_GEN[d.getMonth()];
  if (d.getFullYear() === now.getFullYear()) {
    return `${day} ${month}`;
  }
  return `${day} ${month} ${d.getFullYear()}`;
}

type Props = {
  applicationId: string;
  candidateFullName?: string | null;
  comments: CommissionApplicationPersonalInfoView["comments"];
  canComment: boolean;
  embedded?: boolean;
  /** После успешного POST — обновить данные родителя (например, перезапрос personal-info). */
  onCommentSaved?: () => void | Promise<void>;
};

export function CommissionCommentBlock({
  applicationId,
  candidateFullName = null,
  comments,
  canComment,
  embedded,
  onCommentSaved,
}: Props) {
  const [text, setText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [isPending, startTransition] = useTransition();

  function onSubmit() {
    const body = text.trim();
    if (!body) return;
    setError(null);
    startTransition(async () => {
      try {
        await createCommissionComment(applicationId, body);
        setText("");
        await onCommentSaved?.();
      } catch (e) {
        setError(e instanceof Error ? e.message : "Не удалось сохранить комментарий");
      }
    });
  }

  const content = (
    <>
      <h3 style={{ margin: 0, fontSize: 20, fontWeight: 550, color: "#262626", letterSpacing: "-0.6px", lineHeight: "20px" }}>
        Комментарий
      </h3>
      {canComment ? (
        <div style={{ display: "grid", gap: 8 }}>
          <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px" }}>
            Хотите что-то отметить?
          </p>
          <div
            style={{
              border: "1px solid #e1e1e1",
              borderRadius: 8,
              overflow: "hidden",
            }}
          >
            <textarea
              value={text}
              placeholder="Введите комментарий"
              onChange={(e) => setText(e.target.value)}
              rows={2}
              style={{
                width: "100%",
                border: "none",
                outline: "none",
                padding: "12px 16px",
                fontSize: 14,
                fontWeight: 350,
                fontFamily: "Inter, sans-serif",
                color: "#262626",
                resize: "vertical",
                background: "transparent",
              }}
            />
          </div>
          <div style={{ width: "100%" }}>
            <button
              type="button"
              className="btn"
              style={{ width: "100%", boxSizing: "border-box" }}
              onClick={onSubmit}
              disabled={isPending || !text.trim()}
            >
              {isPending ? "Сохранение..." : "Добавить"}
            </button>
          </div>
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262" }}>
          Комментирование недоступно.
        </p>
      )}
      {error ? <p style={{ margin: 0, fontSize: 13, fontWeight: 350, color: "#e53935" }}>{error}</p> : null}
      {comments.length > 0 ? (
        <div style={{ display: "grid", gap: 10 }}>
          {comments.map((comment) => (
            <article key={comment.id} style={{ borderTop: "1px solid #e1e1e1", paddingTop: 10 }}>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#262626" }}>{comment.text}</p>
                <p style={{ margin: "4px 0 0", fontSize: 12, fontWeight: 350, color: "#626262" }}>
                {comment.authorName} · {formatCommentTimestamp(comment.createdAt, candidateFullName)}
                </p>
            </article>
          ))}
        </div>
      ) : null}
    </>
  );

  if (embedded) return content;

  return (
    <section className="card" style={{ display: "grid", gap: 12 }}>
      {content}
    </section>
  );
}
