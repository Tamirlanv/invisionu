"use client";

import Image from "next/image";
import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { motivationSchema } from "@/lib/validation";
import {
  MAX_MOTIVATION_LETTER_LENGTH,
  MIN_MOTIVATION_LETTER_LENGTH,
  getMotivationLetterCharCount,
  handleMotivationPasteMeta,
  normalizeMotivationLetter,
  trimToMotivationMax,
  validateMotivationLetter,
} from "@/lib/motivation-letter";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import { MotivationInstructionModal } from "@/components/application/MotivationInstructionModal";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import formStyles from "@/components/application/form-ui.module.css";
import styles from "./page.module.css";

const motivationPageSchema = motivationSchema.extend({
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_parent: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
});

type MotivationForm = z.infer<typeof motivationPageSchema>;
type MotivationPayload = z.infer<typeof motivationSchema>;

export default function MotivationPage() {
  const router = useRouter();
  const [msg, setMsg] = useState<string | null>(null);
  const [instructionOpen, setInstructionOpen] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    setValue,
    control,
    watch,
    formState: { isSubmitting },
  } = useForm<MotivationForm>({
    resolver: zodResolver(motivationPageSchema),
    defaultValues: {
      narrative: "",
      was_pasted: false,
      paste_count: 0,
      last_pasted_at: null,
      consent_privacy: false,
      consent_parent: false,
    },
  });

  const narrative = watch("narrative") ?? "";
  const wasPasted = watch("was_pasted") ?? false;
  const pasteCount = watch("paste_count") ?? 0;
  const lastPastedAt = watch("last_pasted_at") ?? null;

  const normalizedNarrative = useMemo(() => trimToMotivationMax(normalizeMotivationLetter(narrative)), [narrative]);
  const charCount = useMemo(() => getMotivationLetterCharCount(normalizedNarrative), [normalizedNarrative]);
  const localValidation = useMemo(() => validateMotivationLetter(normalizedNarrative), [normalizedNarrative]);

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{ sections: Record<string, { payload: unknown }> }>(
          "/candidates/me/application",
          2 * 60 * 1000,
        );
        const raw = app.sections.motivation_goals?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        reset({
          narrative: String(raw.narrative ?? ""),
          was_pasted: Boolean(raw.was_pasted ?? false),
          paste_count:
            typeof raw.paste_count === "number" && raw.paste_count >= 0 ? Math.floor(raw.paste_count) : 0,
          last_pasted_at: raw.last_pasted_at ? String(raw.last_pasted_at) : null,
          consent_privacy: false,
          consent_parent: false,
        });
      } catch {
        setMsg("Не удалось загрузить мотивационное письмо. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  async function saveDraft() {
    setMsg(null);
    try {
      const payload: MotivationPayload = {
        narrative: normalizedNarrative,
        was_pasted: wasPasted,
        paste_count: pasteCount,
        last_pasted_at: lastPastedAt,
      };
      await apiFetch("/candidates/me/application/sections/motivation_goals", {
        method: "PATCH",
        json: { payload },
      });
      bustApiCache("/candidates/me");
      setMsg("Черновик сохранен.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить черновик");
    }
  }

  async function onSubmit(data: MotivationForm) {
    setMsg(null);
    const payload: MotivationPayload = {
      narrative: trimToMotivationMax(normalizeMotivationLetter(data.narrative)),
      was_pasted: data.was_pasted,
      paste_count: data.paste_count,
      last_pasted_at: data.last_pasted_at ?? null,
    };
    try {
      await apiFetch("/candidates/me/application/sections/motivation_goals", {
        method: "PATCH",
        json: { payload },
      });
      bustApiCache("/candidates/me");
      router.push("/application/growth");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  const narrativeReg = register("narrative");

  return (
    <>
      <MotivationInstructionModal open={instructionOpen} onClose={() => setInstructionOpen(false)} />
      <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <FormSection title="Мотивационное письмо">
        <div className={styles.headRow}>
          <p className={styles.description}>
            Опишите, почему вы хотите поступить в inVision U, что вас мотивирует развиваться и каким вы видите свое
            будущее. Нам важно понять ваш личный опыт, ценности, готовность учиться, брать ответственность и влиять на
            окружающих.
          </p>
          <button
            type="button"
            className={`btn ${styles.instructionBtn}`}
            onClick={() => setInstructionOpen(true)}
            aria-haspopup="dialog"
          >
            <Image
              src="/assets/icons/codex_file.svg"
              alt=""
              width={14}
              height={14}
              className={styles.instructionBtnIcon}
              unoptimized
              aria-hidden
            />
            Инструкция
          </button>
        </div>

        <textarea
          {...narrativeReg}
          className={styles.textarea}
          placeholder="Напишите мотивационное письмо"
          value={narrative}
          onChange={(e) => {
            const next = trimToMotivationMax(normalizeMotivationLetter(e.target.value));
            setValue("narrative", next, { shouldDirty: true, shouldValidate: true });
          }}
          onPaste={() => {
            const meta = handleMotivationPasteMeta({
              wasPasted,
              pasteCount,
              lastPastedAt,
            });
            setValue("was_pasted", meta.wasPasted, { shouldDirty: true });
            setValue("paste_count", meta.pasteCount, { shouldDirty: true });
            setValue("last_pasted_at", meta.lastPastedAt, { shouldDirty: true });
          }}
          maxLength={MAX_MOTIVATION_LETTER_LENGTH}
          aria-invalid={Boolean(narrative.trim()) && !localValidation.isValid}
        />

        <input type="hidden" {...register("was_pasted")} />
        <input type="hidden" {...register("paste_count", { valueAsNumber: true })} />
        <input type="hidden" {...register("last_pasted_at")} />

        <div className={styles.counterRow}>
          <span className={styles.counter}>
            {charCount}/{MAX_MOTIVATION_LETTER_LENGTH} символов
          </span>
          <span className={styles.counterHint}>Минимум {MIN_MOTIVATION_LETTER_LENGTH} символов</span>
        </div>

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

      <Divider />

      {msg ? <p className={msg.includes("Не удалось") ? "error" : "muted"}>{msg}</p> : null}

      <div className={formStyles.formFooter}>
        <button type="button" className="btn secondary" onClick={() => void saveDraft()} disabled={isSubmitting}>
          Сохранить черновик
        </button>
        <button type="submit" className="btn" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Далее"}
        </button>
      </div>
      </form>
    </>
  );
}
