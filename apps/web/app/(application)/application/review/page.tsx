"use client";

import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import {
  applicationStageRu,
  applicationStateRu,
  documentTypeRu,
  sectionKeyRu,
  verificationStatusRu,
} from "@/lib/labels";

type Review = {
  application_id: string;
  state: string;
  current_stage: string;
  locked: boolean;
  completion_percentage: number;
  missing_sections: string[];
  sections: Record<string, { is_complete: boolean; payload: unknown }>;
  documents: {
    id: string;
    document_type: string;
    original_filename: string;
    verification_status: string;
  }[];
  required_sections: string[];
};

export default function ReviewPage() {
  const [data, setData] = useState<Review | null>(null);
  const [me, setMe] = useState<{ email_verified: boolean } | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [r, m] = await Promise.all([
        apiFetch<Review>("/candidates/me/application/review"),
        apiFetch<{ user: { email_verified: boolean } }>("/auth/me"),
      ]);
      setData(r);
      setMe(m.user);
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function submitApp() {
    setMsg(null);
    try {
      await apiFetch("/candidates/me/application/submit", { method: "POST" });
      setMsg("Заявление успешно подана.");
      await load();
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
      } else {
        setMsg("Не удалось отправить");
      }
    }
  }

  if (err || !data) {
    return <p className="muted">{err || "Загрузка…"}</p>;
  }

  const canSubmit =
    data.completion_percentage >= 100 &&
    data.missing_sections.length === 0 &&
    !data.locked &&
    me?.email_verified;

  return (
    <div className="card grid" style={{ maxWidth: 800 }}>
      <h1 className="h1" style={{ fontSize: 22 }}>
        Проверка и отправка
      </h1>
      <p className="muted" style={{ margin: 0 }}>
        Заполнено: {data.completion_percentage}% · Состояние: {applicationStateRu(data.state)} · Этап:{" "}
        {applicationStageRu(data.current_stage)}
      </p>
      {!me?.email_verified && (
        <div className="error">Перед финальной отправкой подтвердите email.</div>
      )}
      {data.missing_sections.length > 0 && (
        <div>
          <h2 className="h2">Не заполнено или неполно</h2>
          <ul>
            {data.missing_sections.map((m) => (
              <li key={m}>{sectionKeyRu(m)}</li>
            ))}
          </ul>
        </div>
      )}
      <div>
        <h2 className="h2">Разделы</h2>
        <ul>
          {data.required_sections.map((k) => (
            <li key={k}>
              {sectionKeyRu(k)}: {data.sections[k]?.is_complete ? "готово" : "не готово"}
            </li>
          ))}
        </ul>
      </div>
      <div>
        <h2 className="h2">Документы</h2>
        {data.documents.length === 0 ? (
          <p className="muted">Документы ещё не загружены.</p>
        ) : (
          <ul>
            {data.documents.map((d) => (
              <li key={d.id}>
                {documentTypeRu(d.document_type)} — {d.original_filename} ({verificationStatusRu(d.verification_status)})
              </li>
            ))}
          </ul>
        )}
      </div>
      {msg && <div className="muted">{msg}</div>}
      <button className="btn" type="button" disabled={!canSubmit} onClick={() => void submitApp()}>
        {data.locked ? "Уже отправлено" : "Отправить заявление"}
      </button>
    </div>
  );
}
