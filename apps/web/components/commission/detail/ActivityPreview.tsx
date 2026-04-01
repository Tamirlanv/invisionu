"use client";

import type { CommissionApplicationDetailView } from "@/lib/commission/types";

export function ActivityPreview({ items }: { items: CommissionApplicationDetailView["recentActivity"] }) {
  if (!items.length) {
    return (
      <section className="card">
        <h3 style={{ marginTop: 0 }}>История</h3>
        <p className="muted">Событий пока нет.</p>
      </section>
    );
  }
  return (
    <section className="card" style={{ display: "grid", gap: 8 }}>
      <h3 style={{ margin: 0 }}>Последние события</h3>
      {items.slice(0, 12).map((a) => (
        <div key={a.id} style={{ borderTop: "1px solid #eee", paddingTop: 8 }}>
          <p style={{ margin: 0, fontSize: 13 }}>{a.event_type}</p>
          <p className="muted" style={{ margin: "4px 0 0", fontSize: 12 }}>
            {a.timestamp} {a.actor_user_id ? `· ${a.actor_user_id}` : ""}
          </p>
        </div>
      ))}
    </section>
  );
}
