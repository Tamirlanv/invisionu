"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { apiFetch, ApiError } from "@/lib/api-client";
import { questionCategoryRu, questionTypeRu } from "@/lib/labels";

type Question = {
  id: string;
  category: string;
  question_type: string;
  prompt: string;
  options: { id: string; label: string }[] | null;
};

export default function InternalTestPage() {
  const [questions, setQuestions] = useState<Question[]>([]);
  const [answers, setAnswers] = useState<Record<string, { text?: string; selected?: string[] }>>({});
  const [msg, setMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const qs = await apiFetch<Question[]>("/internal-test/questions");
      setQuestions(qs);
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
      }
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  function setText(id: string, text: string) {
    setAnswers((a) => ({ ...a, [id]: { ...a[id], text } }));
  }

  function toggleMulti(id: string, optId: string) {
    setAnswers((a) => {
      const cur = new Set(a[id]?.selected || []);
      if (cur.has(optId)) {
        cur.delete(optId);
      } else {
        cur.add(optId);
      }
      return { ...a, [id]: { ...a[id], selected: Array.from(cur) } };
    });
  }

  async function saveDraft() {
    setMsg(null);
    const payload = questions.map((q) => {
      const a = answers[q.id] || {};
      if (q.question_type === "text") {
        return { question_id: q.id, text_answer: a.text || "" };
      }
      if (q.question_type === "single_choice") {
        return { question_id: q.id, selected_options: a.selected?.[0] ? [a.selected[0]] : [] };
      }
      return { question_id: q.id, selected_options: a.selected || [] };
    });
    try {
      await apiFetch("/internal-test/answers", { method: "POST", json: { answers: payload } });
      setMsg("Черновик сохранён.");
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
      }
    }
  }

  async function submitFinal() {
    setMsg(null);
    try {
      await saveDraft();
      await apiFetch("/internal-test/submit", { method: "POST" });
      setMsg("Внутренний тест отправлен.");
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
      }
    }
  }

  return (
    <div className="card grid" style={{ maxWidth: 720 }}>
      <h1 className="h1" style={{ fontSize: 20 }}>
        Внутренний тест
      </h1>
      <p className="muted" style={{ margin: 0 }}>
        Сохраняйте черновик по ходу. Отправка один раз — после отправки ответы нельзя изменить.
      </p>
      {questions.map((q) => (
        <div key={q.id} className="card grid" style={{ background: "rgba(0,0,0,0.2)" }}>
          <div className="muted" style={{ fontSize: 12 }}>
            {questionCategoryRu(q.category)} · {questionTypeRu(q.question_type)}
          </div>
          <div>{q.prompt}</div>
          {q.question_type === "text" && (
            <textarea
              className="input"
              rows={5}
              value={answers[q.id]?.text || ""}
              onChange={(e) => setText(q.id, e.target.value)}
            />
          )}
          {q.question_type === "single_choice" && q.options && (
            <div className="grid" style={{ gap: 8 }}>
              {q.options.map((o) => (
                <label key={o.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="radio"
                    name={q.id}
                    checked={(answers[q.id]?.selected || [])[0] === o.id}
                    onChange={() => setAnswers((a) => ({ ...a, [q.id]: { selected: [o.id] } }))}
                  />
                  {o.label}
                </label>
              ))}
            </div>
          )}
          {q.question_type === "multi_choice" && q.options && (
            <div className="grid" style={{ gap: 8 }}>
              {q.options.map((o) => (
                <label key={o.id} style={{ display: "flex", gap: 8, alignItems: "center" }}>
                  <input
                    type="checkbox"
                    checked={(answers[q.id]?.selected || []).includes(o.id)}
                    onChange={() => toggleMulti(q.id, o.id)}
                  />
                  {o.label}
                </label>
              ))}
            </div>
          )}
        </div>
      ))}
      {msg && <div className="muted">{msg}</div>}
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button className="btn secondary" type="button" onClick={() => void saveDraft()}>
          Сохранить черновик
        </button>
        <button className="btn" type="button" onClick={() => void submitFinal()}>
          Отправить тест
        </button>
        <Link className="btn secondary" href="/application/social-status">
          Далее
        </Link>
      </div>
    </div>
  );
}
