"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import { apiFetch, bustApiCache, ApiError } from "@/lib/api-client";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import {
  PERSONALITY_QUESTIONS,
  buildInternalTestAnswerPayload,
  buildPersonalityQuestionMappings,
  mapServerAnswersToUiRecord,
  type AnswerKey,
  type Lang,
  type ServerInternalTestQuestion,
} from "@/lib/personality-profile";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import formStyles from "@/components/application/form-ui.module.css";
import styles from "./page.module.css";

type DraftShape = {
  answers: Record<string, AnswerKey | undefined>;
  consent_privacy: boolean;
  consent_parent: boolean;
};

type SavedAnswersResponse = {
  answers: Array<{
    question_id: string;
    text_answer?: string | null;
    selected_options?: string[];
    is_finalized?: boolean;
  }>;
  consent_privacy: boolean;
  consent_parent: boolean;
};

export default function InternalTestPage() {
  const router = useRouter();
  const [lang, setLang] = useState<Lang>("ru");
  const [answers, setAnswers] = useState<Record<string, AnswerKey | undefined>>({});
  const [msg, setMsg] = useState<string | null>(null);
  const [isMsgError, setIsMsgError] = useState(false);
  const [saving, setSaving] = useState(false);
  const [consentPrivacy, setConsentPrivacy] = useState(false);
  const [consentParent, setConsentParent] = useState(false);
  const [consentErrors, setConsentErrors] = useState({ privacy: false, parent: false });
  const [syncState, setSyncState] = useState<"loading" | "ready" | "error">("loading");
  const [syncError, setSyncError] = useState<string | null>(null);
  const [maps, setMaps] = useState<{
    uiToServer: Map<string, string>;
    serverToUi: Map<string, string>;
  } | null>(null);

  const questions = PERSONALITY_QUESTIONS;
  const total = questions.length;
  const answeredCount = useMemo(
    () => questions.reduce((n, q) => (answers[q.id] ? n + 1 : n), 0),
    [answers, questions],
  );
  const progressPct = total ? Math.round((answeredCount / total) * 100) : 0;

  useEffect(() => {
    let cancelled = false;
    async function load() {
      const local = loadDraft<DraftShape | Record<string, AnswerKey | undefined>>("internal_test");
      const hasStructuredLocal = Boolean(local && typeof local === "object" && "answers" in local);
      if (local && typeof local === "object") {
        if ("answers" in local && typeof local.answers === "object") {
          const d = local as DraftShape;
          setAnswers(d.answers ?? {});
          setConsentPrivacy(Boolean(d.consent_privacy));
          setConsentParent(Boolean(d.consent_parent));
        } else {
          setAnswers(local as Record<string, AnswerKey | undefined>);
        }
      }

      try {
        const serverQs = await apiFetch<ServerInternalTestQuestion[]>("/internal-test/questions");
        if (cancelled) return;
        const mapping = buildPersonalityQuestionMappings(PERSONALITY_QUESTIONS, serverQs);

        if (!mapping.ok) {
          if (!cancelled) {
            setSyncError(mapping.error);
            setSyncState("error");
          }
          return;
        }

        if (!cancelled) {
          setMaps({ uiToServer: mapping.uiToServer, serverToUi: mapping.serverToUi });
          setSyncState("ready");
          setSyncError(null);
        }

        try {
          const saved = await apiFetch<SavedAnswersResponse>("/internal-test/answers");
          if (cancelled) return;
          const fromApi = mapServerAnswersToUiRecord(mapping.serverToUi, saved.answers ?? []);
          setAnswers((prev) => ({ ...fromApi, ...prev }));
          if (!hasStructuredLocal) {
            setConsentPrivacy(Boolean(saved.consent_privacy));
            setConsentParent(Boolean(saved.consent_parent));
          }
        } catch {
          // Keep local draft as fallback.
        }
      } catch {
        if (!cancelled) {
          setSyncError("Не удалось загрузить вопросы теста. Попробуйте обновить страницу.");
          setSyncState("error");
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function saveDraft() {
    setMsg(null);
    setIsMsgError(false);
    if (syncState !== "ready" || !maps) {
      setMsg(syncError ?? "Тест временно недоступен: рассинхрон вопросов.");
      setIsMsgError(true);
      return;
    }
    setSaving(true);
    saveDraftLocal("internal_test", { answers, consent_privacy: consentPrivacy, consent_parent: consentParent } as DraftShape);
    const payload = buildInternalTestAnswerPayload(questions, answers, maps.uiToServer);
    try {
      await apiFetch("/internal-test/answers", {
        method: "POST",
        json: { answers: payload, consent_privacy: consentPrivacy, consent_parent: consentParent },
      });
      bustApiCache("/candidates/me");
      setMsg("Черновик сохранён.");
      setIsMsgError(false);
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось сохранить черновик.");
      setIsMsgError(true);
    } finally {
      setSaving(false);
    }
  }

  async function handleNext() {
    const errors = { privacy: !consentPrivacy, parent: !consentParent };
    setConsentErrors(errors);
    if (errors.privacy || errors.parent) {
      setMsg(null);
      return;
    }
    setMsg(null);
    setIsMsgError(false);
    if (syncState !== "ready" || !maps) {
      setMsg(syncError ?? "Тест временно недоступен: рассинхрон вопросов.");
      setIsMsgError(true);
      return;
    }
    setSaving(true);
    saveDraftLocal("internal_test", { answers, consent_privacy: consentPrivacy, consent_parent: consentParent } as DraftShape);
    const payload = buildInternalTestAnswerPayload(questions, answers, maps.uiToServer);
    try {
      await apiFetch("/internal-test/answers", {
        method: "POST",
        json: { answers: payload, consent_privacy: consentPrivacy, consent_parent: consentParent },
      });
      bustApiCache("/candidates/me");
      clearDraft("internal_test");
      router.push("/application/motivation");
    } catch (e) {
      setMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось сохранить ответы теста.");
      setIsMsgError(true);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className={styles.root}>
      <section className={styles.intro}>
        {syncState === "loading" ? (
          <p className={styles.description} role="status">
            Загрузка вопросов теста…
          </p>
        ) : null}
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
          checked={consentPrivacy}
          onChange={(checked) => {
            setConsentPrivacy(checked);
            if (checked) setConsentErrors((prev) => ({ ...prev, privacy: false }));
            saveDraftLocal("internal_test", { answers, consent_privacy: checked, consent_parent: consentParent } as DraftShape);
          }}
        >
          Отправляя эту форму, вы соглашаетесь на обработку ваших персональных данных в соответствии с нашей{" "}
          <Link href="/privacy">Политикой конфиденциальности</Link>
        </ConsentCheckbox>
        {consentErrors.privacy && (
          <p className="error" style={{ margin: 0 }}>Необходимо согласие</p>
        )}
        <ConsentCheckbox
          checked={consentParent}
          onChange={(checked) => {
            setConsentParent(checked);
            if (checked) setConsentErrors((prev) => ({ ...prev, parent: false }));
            saveDraftLocal("internal_test", { answers, consent_privacy: consentPrivacy, consent_parent: checked } as DraftShape);
          }}
        >
          Если участнику меньше 18 лет, эту анкету должен заполнить его родитель или законный представитель.
          Продолжая, вы подтверждаете, что вы либо (a) участник в возрасте 18 лет или старше, либо (b) родитель
          или законный представитель, заполняющий эту форму от имени несовершеннолетнего
        </ConsentCheckbox>
        {consentErrors.parent && (
          <p className="error" style={{ margin: 0 }}>Необходимо подтверждение</p>
        )}
      </section>

      <Divider />

      {syncState === "error" && syncError ? (
        <p className="error" role="alert">
          {syncError}
        </p>
      ) : null}

      {msg ? (
        <p className={isMsgError ? "error" : styles.successMsg} role="status">
          {msg}
        </p>
      ) : null}

      <section className={`${styles.actions} ${formStyles.formFooter}`}>
        <button
          className="btn secondary"
          type="button"
          onClick={() => void saveDraft()}
          disabled={saving || syncState !== "ready"}
        >
          {saving ? "Сохранение..." : "Сохранить черновик"}
        </button>
        <button className="btn" type="button" onClick={() => void handleNext()} disabled={saving || syncState !== "ready"}>
          Далее
        </button>
      </section>
    </div>
  );
}
