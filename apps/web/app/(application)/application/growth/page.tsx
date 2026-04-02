"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError, apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { growthPathPageSchema } from "@/lib/validation";
import { GROWTH_CHAR_LIMITS, GROWTH_QUESTIONS, type GrowthQuestionId } from "@/lib/growth-path/constants";
import {
  growthCharCount,
  normalizeGrowthText,
  trimToMaxForQuestion,
  validateGrowthAnswerLength,
} from "@/lib/growth-path/text";
import { usePathQuestionField } from "@/lib/growth-path/usePathQuestionField";
import type { GrowthAnswerMetaState } from "@/lib/growth-path/types";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import formStyles from "@/components/application/form-ui.module.css";
import styles from "./page.module.css";

type GrowthForm = z.infer<typeof growthPathPageSchema>;

function buildPayload(data: GrowthForm, metaByQ: Record<GrowthQuestionId, GrowthAnswerMetaState>) {
  const answers: Record<
    string,
    {
      text: string;
      meta: GrowthAnswerMetaState;
    }
  > = {};
  for (const id of ["q1", "q2", "q3", "q4", "q5"] as const) {
    const text = normalizeGrowthText(data.answers[id].text);
    const m = metaByQ[id];
    answers[id] = {
      text,
      meta: { ...m },
    };
  }
  return {
    payload: {
      answers,
      consent_privacy: data.consent_privacy,
      consent_parent: data.consent_parent,
    },
  };
}

export default function GrowthPage() {
  const router = useRouter();
  const [msg, setMsg] = useState<string | null>(null);

  const q1 = usePathQuestionField("q1");
  const q2 = usePathQuestionField("q2");
  const q3 = usePathQuestionField("q3");
  const q4 = usePathQuestionField("q4");
  const q5 = usePathQuestionField("q5");

  const fieldById: Record<GrowthQuestionId, typeof q1> = {
    q1,
    q2,
    q3,
    q4,
    q5,
  };

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    getValues,
    trigger,
    control,
    watch,
    formState: { isSubmitting, errors },
  } = useForm<GrowthForm>({
    resolver: zodResolver(growthPathPageSchema),
    defaultValues: {
      answers: {
        q1: { text: "" },
        q2: { text: "" },
        q3: { text: "" },
        q4: { text: "" },
        q5: { text: "" },
      },
      consent_privacy: false,
      consent_parent: false,
    },
  });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{ sections: Record<string, { payload: unknown }> }>(
          "/candidates/me/application",
          2 * 60 * 1000,
        );
        const raw = app.sections.growth_journey?.payload as Record<string, unknown> | undefined;
        let answersRaw: Record<string, { text?: string; meta?: unknown } | undefined> | undefined;
        if (raw) {
          answersRaw = raw.answers as typeof answersRaw;
          if (!answersRaw && raw.narrative != null) {
            const n = String(raw.narrative ?? "");
            answersRaw = {
              q1: { text: n },
              q2: { text: "" },
              q3: { text: "" },
              q4: { text: "" },
              q5: { text: "" },
            };
          }
        }
        const apiValues: Partial<GrowthForm> = answersRaw
          ? {
              answers: {
                q1: { text: String(answersRaw.q1?.text ?? "") },
                q2: { text: String(answersRaw.q2?.text ?? "") },
                q3: { text: String(answersRaw.q3?.text ?? "") },
                q4: { text: String(answersRaw.q4?.text ?? "") },
                q5: { text: String(answersRaw.q5?.text ?? "") },
              },
              consent_privacy: raw ? Boolean((raw as Record<string, unknown>).consent_privacy) : false,
              consent_parent: raw ? Boolean((raw as Record<string, unknown>).consent_parent) : false,
            }
          : {};
        const local = loadDraft<GrowthForm>("growth");
        const merged = {
          answers: {
            q1: { text: "" },
            q2: { text: "" },
            q3: { text: "" },
            q4: { text: "" },
            q5: { text: "" },
          },
          ...apiValues,
          ...local,
        } as GrowthForm;
        reset(merged);
        if (answersRaw) {
          q1.hydrateFromApi(answersRaw.q1?.meta);
          q2.hydrateFromApi(answersRaw.q2?.meta);
          q3.hydrateFromApi(answersRaw.q3?.meta);
          q4.hydrateFromApi(answersRaw.q4?.meta);
          q5.hydrateFromApi(answersRaw.q5?.meta);
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        setMsg("Не удалось загрузить раздел. Обновите страницу.");
      }
    }
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- hydrate once on mount; field hooks are stable enough for hydration
  }, [reset]);

  useEffect(() => {
    const sub = watch((_, { name }) => {
      if (name === "consent_privacy" || name === "consent_parent") {
        saveDraftLocal("growth", getValues());
      }
    });
    return () => sub.unsubscribe();
  }, [watch, getValues]);

  function metaRecord(): Record<GrowthQuestionId, GrowthAnswerMetaState> {
    return {
      q1: q1.meta,
      q2: q2.meta,
      q3: q3.meta,
      q4: q4.meta,
      q5: q5.meta,
    };
  }

  async function saveDraft() {
    setMsg(null);
    const data = getValues();
    saveDraftLocal("growth", data);
    const ok = await trigger();
    if (!ok) {
      setMsg("Заполните все поля в указанных пределах и отметьте согласия.");
      return;
    }
    try {
      await apiFetch("/candidates/me/application/sections/growth_journey", {
        method: "PATCH",
        json: buildPayload(data, metaRecord()),
      });
      bustApiCache("/candidates/me");
      setMsg("Черновик сохранен.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить черновик");
    }
  }

  async function onSubmit(data: GrowthForm) {
    setMsg(null);
    try {
      await apiFetch("/candidates/me/application/sections/growth_journey", {
        method: "PATCH",
        json: buildPayload(data, metaRecord()),
      });
      bustApiCache("/candidates/me");
      clearDraft("growth");
      router.push("/application/achievements");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <FormSection title="Путь">
        <div className={styles.headRow}>
          <p className={styles.description}>
            Расскажите о своём опыте, трудностях, инициативах и достижениях — нам важно увидеть, как вы действуете и
            учитесь на практике.
          </p>
        </div>

        <hr className={styles.questionRule} aria-hidden />

        {GROWTH_QUESTIONS.map(({ id, label }, index) => {
          const limits = GROWTH_CHAR_LIMITS[id];
          const field = fieldById[id];
          const text = watch(`answers.${id}.text`) ?? "";
          const normalizedLen = growthCharCount(text);
          const lenState = validateGrowthAnswerLength(id, text);
          const showInvalidOutline = Boolean(normalizedLen > 0 && !lenState.ok);
          const textReg = register(`answers.${id}.text`);
          const isLast = index === GROWTH_QUESTIONS.length - 1;

          return (
            <div key={id}>
              <div className={styles.questionBlock}>
              <p className={styles.questionLabel}>{label}</p>
              <textarea
                {...textReg}
                className={styles.textarea}
                placeholder="Введите ответ"
                value={text}
                onFocus={field.onFocus}
                onBeforeInput={field.onBeforeInput}
                onPaste={() => {
                  field.onPaste();
                }}
                onChange={(e) => {
                  const prev = getValues(`answers.${id}.text`) ?? "";
                  const next = trimToMaxForQuestion(id, normalizeGrowthText(e.target.value));
                  setValue(`answers.${id}.text`, next, { shouldDirty: true, shouldValidate: true });
                  field.onChangeValue(next, prev);
                }}
                onBlur={(e) => {
                  field.onBlurValue(e.target.value);
                  textReg.onBlur(e);
                }}
                aria-invalid={showInvalidOutline}
              />
              <div className={styles.counterRow}>
                <span className={styles.counter}>
                  {normalizedLen}/{limits.max} символов
                </span>
                <span className={styles.counterHint}>
                  От {limits.min} до {limits.max} символов
                </span>
              </div>
              {errors.answers?.[id]?.text ? (
                <p className="error" style={{ margin: "8px 0 0", fontSize: 14 }}>
                  {errors.answers[id]?.text?.message}
                </p>
              ) : null}
              </div>
              {!isLast ? <hr className={styles.questionRule} aria-hidden /> : null}
            </div>
          );
        })}
      </FormSection>

      <Divider />

      <div className={formStyles.consentBlock}>
        <Controller
          name="consent_privacy"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Отправляя эту форму, вы соглашаетесь на обработку ваших персональных данных в соответствии с нашей{" "}
              <a href="/privacy">Политикой конфиденциальности</a>
            </ConsentCheckbox>
          )}
        />
        <Controller
          name="consent_parent"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Если участнику меньше 18 лет, эту анкету должен заполнить его родитель или законный представитель.
              Продолжая, вы подтверждаете, что вы либо (a) участник в возрасте 18 лет или старше, либо (b) родитель
              или законный представитель, заполняющий эту форму от имени несовершеннолетнего
            </ConsentCheckbox>
          )}
        />
      </div>

      {errors.consent_privacy ? <p className="error">{errors.consent_privacy.message}</p> : null}
      {errors.consent_parent ? <p className="error">{errors.consent_parent.message}</p> : null}

      <Divider />

      {msg ? <p className={msg.includes("Не удалось") || msg.includes("Заполните") ? "error" : "muted"}>{msg}</p> : null}

      <div className={formStyles.formFooter}>
        <button type="button" className="btn secondary" onClick={() => void saveDraft()} disabled={isSubmitting}>
          Сохранить черновик
        </button>
        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Далее"}
        </button>
      </div>
    </form>
  );
}
