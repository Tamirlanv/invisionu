"use client";

import { useState } from "react";
import type { CommissionApplicationDetailView } from "@/lib/commission/types";

const TABS = [
  { id: "personal", label: "Личная информация" },
  { id: "test", label: "Тест" },
  { id: "motivation", label: "Мотивация" },
  { id: "path", label: "Путь" },
  { id: "achievements", label: "Достижения" },
] as const;

type TabId = (typeof TABS)[number]["id"];

function KeyValueBlock({ title, data }: { title: string; data: Record<string, unknown> | null | undefined }) {
  if (!data || Object.keys(data).length === 0) {
    return (
      <p className="muted" style={{ margin: 0 }}>
        Нет данных.
      </p>
    );
  }
  return (
    <div style={{ display: "grid", gap: 6 }}>
      <h4 style={{ margin: 0 }}>{title}</h4>
      <ul style={{ margin: 0, paddingLeft: 18 }}>
        {Object.entries(data).map(([k, v]) => (
          <li key={k} style={{ wordBreak: "break-word" }}>
            <strong>{k}:</strong> {typeof v === "object" ? JSON.stringify(v) : String(v)}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function ApplicationTabs({ detail }: { detail: CommissionApplicationDetailView }) {
  const [tab, setTab] = useState<TabId>("personal");

  return (
    <section className="card" style={{ display: "grid", gap: 12 }}>
      <nav style={{ display: "flex", gap: 8, flexWrap: "wrap" }} aria-label="Вкладки заявки">
        {TABS.map((t) => (
          <button key={t.id} type="button" className={tab === t.id ? "btn" : "btn secondary"} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>

      {tab === "personal" ? (
        <div style={{ display: "grid", gap: 16 }}>
          <KeyValueBlock title="Основная информация" data={detail.personalInfo.basicInfo} />
          <KeyValueBlock title="Контакты" data={detail.personalInfo.contacts} />
          {detail.personalInfo.guardians?.length ? (
            <div>
              <h4 style={{ margin: "0 0 8px" }}>Родители / опекуны</h4>
              {detail.personalInfo.guardians.map((g, i) => (
                <KeyValueBlock key={i} title={`Опекун ${i + 1}`} data={g} />
              ))}
            </div>
          ) : null}
          <KeyValueBlock title="Адрес" data={detail.personalInfo.address} />
          <KeyValueBlock title="Образование" data={detail.personalInfo.education} />
        </div>
      ) : null}

      {tab === "test" ? (
        <div>
          {detail.test && Object.keys(detail.test).length ? (
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 13 }}>{JSON.stringify(detail.test, null, 2)}</pre>
          ) : (
            <p className="muted">Нет данных теста.</p>
          )}
        </div>
      ) : null}

      {tab === "motivation" ? (
        <div>
          {detail.motivation ? (
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 13 }}>{JSON.stringify(detail.motivation, null, 2)}</pre>
          ) : (
            <p className="muted">Мотивационное письмо не заполнено.</p>
          )}
        </div>
      ) : null}

      {tab === "path" ? (
        <div style={{ display: "grid", gap: 12 }}>
          {!detail.path ? <p className="muted">Секция «Путь» пуста.</p> : null}
          {detail.path?.answers?.map((a) => (
            <article key={a.questionKey}>
              <h4 style={{ margin: "0 0 6px" }}>{a.questionTitle}</h4>
              <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{a.text}</p>
            </article>
          ))}
          {detail.path?.summary ? (
            <div>
              <h4 style={{ margin: "0 0 6px" }}>Сводка (служебно)</h4>
              <p style={{ margin: 0, whiteSpace: "pre-wrap" }}>{detail.path.summary}</p>
            </div>
          ) : null}
        </div>
      ) : null}

      {tab === "achievements" ? (
        <div>
          {detail.achievements && Object.keys(detail.achievements).length ? (
            <pre style={{ whiteSpace: "pre-wrap", margin: 0, fontSize: 13 }}>{JSON.stringify(detail.achievements, null, 2)}</pre>
          ) : (
            <p className="muted">Достижения не заполнены.</p>
          )}
        </div>
      ) : null}
    </section>
  );
}
