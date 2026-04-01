"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { apiFetch, bustApiCache, ApiError } from "@/lib/api-client";
import { PERSONALITY_QUESTIONS, type AnswerKey, type Lang } from "@/lib/personality-profile";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import formStyles from "@/components/application/form-ui.module.css";
import styles from "./page.module.css";

export default function InternalTestPage() {
  const [lang, setLang] = useState<Lang>("ru");
  const [answers, setAnswers] = useState<Record<string, AnswerKey | undefined>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [isMsgError, setIsMsgError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [agreements, setAgreements] = useState({ privacy: false, parent: false });

  const questions = PERSONALITY_QUESTIONS;
  const total = questions.length;
  const answeredCount = useMemo(
    () => questions.reduce((n, q) => (answers[q.id] ? n + 1 : n), 0),
    [answers, questions],
  );
  const progressPct = total ? Math.round((answeredCount / total) * 100) : 0;

  async function saveDraft() {
    setMsg(null);
    setIsMsgError(false);
    setSaving(true);
    const payload = questions
      .filter((q) => Boolean(answers[q.id]))
      .map((q) => ({ question_id: q.id, selected_options: [answers[q.id] as AnswerKey] }));
    try {
      await apiFetch("/internal-test/answers", { method: "POST", json: { answers: payload } });
      bustApiCache("/candidates/me");
      setMsg("Черновик сохранён.");
      setIsMsgError(false);
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
        setIsMsgError(true);
      }
    } finally {
      setSaving(false);
    }
  }

  async function submitFinal() {
    setMsg(null);
    setIsMsgError(false);
    try {
      if (answeredCount !== total) {
        setMsg("Ответьте на все вопросы перед отправкой.");
        setIsMsgError(true);
        return;
      }
      setSubmitting(true);
      // Ensure backend has all answers saved (its validation requires selected_options present).
      const payload = questions.map((q) => ({ question_id: q.id, selected_options: [answers[q.id] as AnswerKey] }));
      await apiFetch("/internal-test/answers", { method: "POST", json: { answers: payload } });
      await apiFetch("/internal-test/submit", { method: "POST" });
      bustApiCache("/candidates/me");
      setMsg("Тест отправлен.");
      setIsMsgError(false);
    } catch (e) {
      if (e instanceof ApiError) {
        setMsg(e.message);
        setIsMsgError(true);
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className={styles.root}>
      <section className={styles.intro}>
        <h1 className={styles.title}>Тест на тип личности</h1>
        <p className={styles.description}>
          Правильных или неправильных ответов нет - мы просто хотим лучше понять вас, ваш образ мышления и то, что
          движет вашими решениями. Будьте честны и доверьтесь своей первой интуиции.
        </p>
      </section>

      <section className={styles.topMeta}>
        <div className={styles.langWrap}>
          <span className={styles.langLabel}>Язык теста</span>
          <PillSegmentedControl
            aria-label="Язык теста"
            options={[
              { value: "ru", label: "RU" },
              { value: "en", label: "EN" },
            ]}
            value={lang}
            onChange={(v) => setLang(v)}
          />
        </div>
        <div className={styles.progressWrap}>
          <div className={styles.progressText}>
            Прогресс: {answeredCount}/{total} ({progressPct}%)
          </div>
          <div className={styles.progressTrack} aria-hidden>
            <div className={styles.progressFill} style={{ width: `${progressPct}%` }} />
          </div>
        </div>
      </section>

      <Divider />

      <section className={styles.questions}>
        {questions.map((q, idx) => {
          const selected = answers[q.id];
          return (
            <div key={q.id}>
              <article className={styles.questionBlock}>
                <h2 className={styles.questionTitle}>
                  <span>{q.index}.</span> <span>{q.text[lang]}</span>
                </h2>
                <div className={styles.options}>
                  {q.options.map((o) => {
                    const checked = selected === o.key;
                    const muted = Boolean(selected) && !checked;
                    return (
                      <button
                        key={o.key}
                        type="button"
                        className={styles.optionBtn}
                        onClick={() => setAnswers((a) => ({ ...a, [q.id]: o.key }))}
                      >
                        <span className={`${styles.checkbox} ${checked ? styles.checkboxChecked : ""}`} aria-hidden />
                        <span className={`${styles.optionText} ${muted ? styles.optionTextMuted : ""}`}>{o.text[lang]}</span>
                      </button>
                    );
                  })}
                </div>
              </article>
              {idx < questions.length - 1 ? <Divider /> : null}
            </div>
          );
        })}
      </section>

      <Divider />

      <section className={styles.consents}>
        <ConsentCheckbox
          checked={agreements.privacy}
          onChange={(checked) => setAgreements((prev) => ({ ...prev, privacy: checked }))}
        >
          Отправляя эту форму, вы соглашаетесь на обработку ваших персональных данных в соответствии с нашей{" "}
          <span className={styles.inlineLink}>Политикой конфиденциальности</span>
          .
        </ConsentCheckbox>
        <ConsentCheckbox
          checked={agreements.parent}
          onChange={(checked) => setAgreements((prev) => ({ ...prev, parent: checked }))}
        >
          Если участнику меньше 18 лет, эту анкету должен заполнить его родитель или законный представитель.
          Продолжая, вы подтверждаете, что вы либо участник 18+, либо родитель или законный представитель.
        </ConsentCheckbox>
      </section>

      <Divider />

      {msg ? (
        <p className={isMsgError ? "error" : styles.successMsg} role="status">
          {msg}
        </p>
      ) : null}

      <section className={`${styles.actions} ${formStyles.formFooter}`}>
        <button className="btn secondary" type="button" onClick={() => void saveDraft()} disabled={saving || submitting}>
          {saving ? "Сохранение..." : "Сохранить черновик"}
        </button>
        <button className="btn secondary" type="button" onClick={() => void submitFinal()} disabled={saving || submitting}>
          {submitting ? "Отправка..." : "Отправить тест"}
        </button>
        <Link className="btn" href="/application/motivation">
          Далее
        </Link>
      </section>
    </div>
  );
}
