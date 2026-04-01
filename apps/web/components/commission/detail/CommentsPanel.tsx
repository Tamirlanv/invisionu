"use client";

import { useState } from "react";
import type { CommissionPermissions } from "@/lib/commission/permissions";
import type { CommissionApplicationDetailView } from "@/lib/commission/types";
import { createApplicationComment } from "@/lib/commission/query";

type Props = {
  detail: CommissionApplicationDetailView;
  permissions: CommissionPermissions;
  onChanged: () => Promise<void>;
  onError: (msg: string) => void;
};

export function CommentsPanel({ detail, permissions, onChanged, onError }: Props) {
  const [text, setText] = useState("");
  const [pending, setPending] = useState(false);

  async function submit() {
    if (!text.trim()) return;
    setPending(true);
    try {
      await createApplicationComment(detail.application_id, text.trim());
      setText("");
      await onChanged();
    } catch (e) {
      onError(e instanceof Error ? e.message : "Не удалось добавить комментарий");
    } finally {
      setPending(false);
    }
  }

  return (
    <section className="card" style={{ display: "grid", gap: 10 }}>
      <h3 style={{ margin: 0 }}>Внутренние комментарии</h3>
      {permissions.canComment ? (
        <div style={{ display: "flex", gap: 8 }}>
          <input className="input" value={text} onChange={(e) => setText(e.target.value)} placeholder="Комментарий для комиссии" />
          <button className="btn secondary" type="button" disabled={pending} onClick={() => void submit()}>
            {pending ? "..." : "Добавить"}
          </button>
        </div>
      ) : null}
      {detail.comments.length === 0 ? <p className="muted">Комментариев пока нет.</p> : null}
      {detail.comments.map((c) => (
        <article key={c.id} style={{ borderTop: "1px solid #eee", paddingTop: 8 }}>
          <p style={{ margin: 0 }}>{c.text}</p>
          <p className="muted" style={{ margin: "4px 0 0" }}>
            {c.createdAt ?? "—"} · {c.authorId ?? "system"}
          </p>
        </article>
      ))}
    </section>
  );
}

