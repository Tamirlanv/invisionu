"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { createCommissionComment } from "@/lib/commission/query";
import type { CommissionApplicationPersonalInfoView } from "@/lib/commission/types";

type Props = {
  applicationId: string;
  comments: CommissionApplicationPersonalInfoView["comments"];
  canComment: boolean;
  embedded?: boolean;
};

export function CommissionCommentBlock({ applicationId, comments, canComment, embedded }: Props) {
  const router = useRouter();
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
        router.refresh();
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
          <p style={{ margin: 0, fontSize: 14, color: "#626262", letterSpacing: "-0.42px" }}>
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
                fontFamily: "Inter, sans-serif",
                color: "#262626",
                resize: "vertical",
                background: "transparent",
              }}
            />
          </div>
          <div>
            <button
              type="button"
              onClick={onSubmit}
              disabled={isPending || !text.trim()}
              style={{
                background: "#98da00",
                color: "#fff",
                border: "none",
                borderRadius: 8,
                padding: "10px 20px",
                fontSize: 14,
                cursor: isPending || !text.trim() ? "not-allowed" : "pointer",
                opacity: isPending || !text.trim() ? 0.5 : 1,
              }}
            >
              {isPending ? "Сохранение..." : "Добавить"}
            </button>
          </div>
        </div>
      ) : (
        <p style={{ margin: 0, fontSize: 14, color: "#626262" }}>
          Комментирование недоступно.
        </p>
      )}
      {error ? <p style={{ margin: 0, fontSize: 13, color: "#e53935" }}>{error}</p> : null}
      {comments.length > 0 ? (
        <div style={{ display: "grid", gap: 10 }}>
          {comments.map((comment) => (
            <article key={comment.id} style={{ borderTop: "1px solid #e1e1e1", paddingTop: 10 }}>
              <p style={{ margin: 0, fontSize: 14, color: "#262626" }}>{comment.text}</p>
              <p style={{ margin: "4px 0 0", fontSize: 12, color: "#626262" }}>
                {comment.authorName} · {comment.createdAt ?? "—"}
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
