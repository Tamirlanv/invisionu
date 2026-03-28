"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import { StageTracker } from "@/components/StageTracker";
import {
  applicationStageRu,
  applicationStateRu,
  documentTypeRu,
  missingItemRu,
} from "@/lib/labels";

type DashboardSummary = {
  candidate_name: string;
  application_id: string;
  application_state: string;
  current_stage: string;
  completion_percentage: number;
  stage_timeline: { to_stage: string; entered_at: string; candidate_visible_note?: string | null }[];
  document_summary: Record<string, number>;
  missing_items: string[];
  recent_updates: { kind: string; at: string; message: string }[];
};

type Me = {
  user: { email: string; email_verified: boolean };
  profile: { first_name: string; last_name: string } | null;
};

function DashboardInner() {
  const params = useSearchParams();
  const welcome = params.get("welcome");
  const [me, setMe] = useState<Me | null>(null);
  const [dash, setDash] = useState<DashboardSummary | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [verifyMsg, setVerifyMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setErr(null);
    try {
      const [m, d] = await Promise.all([
        apiFetch<Me>("/auth/me"),
        apiFetch<DashboardSummary>("/candidates/me/dashboard-summary"),
      ]);
      setMe(m);
      setDash(d);
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
      } else {
        setErr("Не удалось загрузить данные");
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function verify() {
    setVerifyMsg(null);
    try {
      await apiFetch("/auth/verify-email", { method: "POST", json: { code } });
      setVerifyMsg("Email подтверждён.");
      setCode("");
      await load();
    } catch (e) {
      if (e instanceof ApiError) {
        setVerifyMsg(e.message);
      } else {
        setVerifyMsg("Не удалось подтвердить");
      }
    }
  }

  if (err) {
    return (
      <div>
        <p className="error">{err}</p>
        <Link href="/login">Войти</Link>
      </div>
    );
  }

  if (!dash || !me) {
    return <p className="muted">Загрузка…</p>;
  }

  return (
    <div className="grid" style={{ gap: 18 }}>
      {welcome && <div className="card">Добро пожаловать — аккаунт готов.</div>}

      <div className="card">
        <h1 className="h1" style={{ fontSize: 22 }}>
          Здравствуйте, {dash.candidate_name}
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          Вы вошли как {me.user.email}
          {me.user.email_verified ? " · email подтверждён" : " · email не подтверждён"}
        </p>
      </div>

      {!me.user.email_verified && (
        <div className="card grid" style={{ maxWidth: 420 }}>
          <h2 className="h2">Подтвердите email</h2>
          <p className="muted" style={{ margin: 0 }}>
            Введите 6-значный код из письма.
          </p>
          <div>
            <label className="label">Код</label>
            <input className="input" value={code} onChange={(e) => setCode(e.target.value)} maxLength={6} />
          </div>
          {verifyMsg && <div className="muted">{verifyMsg}</div>}
          <button className="btn" type="button" onClick={() => void verify()}>
            Подтвердить
          </button>
        </div>
      )}

      <div className="card grid">
        <h2 className="h2">Статус заявления</h2>
        <div style={{ display: "flex", flexWrap: "wrap", gap: 12, alignItems: "baseline" }}>
          <span style={{ fontSize: 22, fontWeight: 700 }}>{dash.completion_percentage}%</span>
          <span className="muted">заполнено</span>
          <span className="muted">·</span>
          <span>
            Состояние: <strong>{applicationStateRu(dash.application_state)}</strong>
          </span>
          <span className="muted">·</span>
          <span>
            Этап: <strong>{applicationStageRu(dash.current_stage)}</strong>
          </span>
        </div>
        <Link className="btn" href="/application/personal">
          Продолжить заявление
        </Link>
      </div>

      <StageTracker />

      <div className="card grid">
        <h2 className="h2">Документы</h2>
        <ul style={{ margin: 0, paddingLeft: 18 }}>
          {Object.entries(dash.document_summary).map(([k, v]) => (
            <li key={k}>
              {documentTypeRu(k)}: {v}
            </li>
          ))}
        </ul>
      </div>

      <div className="card grid">
        <h2 className="h2">Что осталось</h2>
        {dash.missing_items.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Нет — обязательные пункты заполнены.
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {dash.missing_items.map((m) => (
              <li key={m}>{missingItemRu(m)}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="card grid">
        <h2 className="h2">Недавние события</h2>
        {dash.recent_updates.length === 0 ? (
          <p className="muted" style={{ margin: 0 }}>
            Пока нет записей.
          </p>
        ) : (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {dash.recent_updates.map((u) => (
              <li key={`${u.at}-${u.message}`}>
                <span className="muted">{u.at}</span> — {u.message}
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  return (
    <Suspense fallback={<p className="muted">Загрузка…</p>}>
      <DashboardInner />
    </Suspense>
  );
}
