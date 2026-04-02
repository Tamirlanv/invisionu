"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, useFieldArray, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError, apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { achievementsSchema } from "@/lib/validation";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import formStyles from "@/components/application/form-ui.module.css";
import styles from "./page.module.css";

type Form = z.infer<typeof achievementsSchema>;

const STATIC_LINKS: { link_type: string; label: string }[] = [
  { link_type: "github", label: "GitHub" },
  { link_type: "behance", label: "Behance" },
  { link_type: "disk", label: "Disk" },
  { link_type: "extra", label: "Дополнительно" },
];

const MAX_TOTAL_LINKS = 8;

function buildDefaults(): Form {
  return {
    achievements_text: "",
    role: "",
    year: "",
    links: STATIC_LINKS.map((s) => ({ ...s, url: "" })),
    consent_privacy: false,
    consent_parent: false,
  };
}

export default function AchievementsPage() {

  const [msg, setMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    watch,
    trigger,
    getValues,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(achievementsSchema),
    defaultValues: buildDefaults(),
  });

  const { fields, append, remove } = useFieldArray({ control, name: "links" });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          sections: Record<string, { payload: unknown }>;
        }>("/candidates/me/application", 2 * 60 * 1000);
        const raw = app.sections.achievements_activities?.payload as Record<string, unknown> | undefined;
        let apiValues: Partial<Form> = {};
        if (raw) {
          const links = Array.isArray(raw.links) ? (raw.links as Form["links"]) : [];
          const mergedLinks = STATIC_LINKS.map((s) => {
            const saved = links.find((l) => l.link_type === s.link_type && !l.url?.startsWith("__dyn__"));
            return { ...s, url: saved?.url ?? "" };
          });
          const extras = links.filter(
            (l) => !STATIC_LINKS.some((s) => s.link_type === l.link_type) || l.link_type === "extra",
          );
          const dynamicExtras = extras.filter((l) => l.link_type === "extra" && !mergedLinks.some((m) => m.url === l.url && m.link_type === "extra"));
          apiValues = {
            achievements_text: typeof raw.achievements_text === "string" ? raw.achievements_text : "",
            role: typeof raw.role === "string" ? raw.role : "",
            year: typeof raw.year === "string" ? raw.year : "",
            links: [...mergedLinks, ...dynamicExtras.map((d) => ({ link_type: "extra", label: "Дополнительно", url: d.url ?? "" }))],
            consent_privacy: Boolean(raw.consent_privacy),
            consent_parent: Boolean(raw.consent_parent),
          };
        }
        const local = loadDraft<Form>("achievements");
        reset({ ...buildDefaults(), ...apiValues, ...local });
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        setMsg("Не удалось загрузить данные. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  useEffect(() => {
    const sub = watch((_, { name }) => {
      if (name === "consent_privacy" || name === "consent_parent") {
        saveDraftLocal("achievements", getValues());
      }
    });
    return () => sub.unsubscribe();
  }, [watch, getValues]);

  function buildPayload(data: Form) {
    return {
      payload: {
        achievements_text: data.achievements_text,
        role: data.role?.trim() || "",
        year: data.year?.trim() || "",
        links: data.links
          .filter((l) => l.url.trim())
          .map((l) => ({ link_type: l.link_type, label: l.label, url: l.url.trim() })),
        consent_privacy: data.consent_privacy,
        consent_parent: data.consent_parent,
      },
    };
  }

  async function saveDraft() {
    setMsg(null);
    const values = getValues();
    saveDraftLocal("achievements", values);
    const ok = await trigger();
    if (!ok) {
      setMsg("Заполните все обязательные поля и отметьте согласия.");
      return;
    }
    try {
      await apiFetch("/candidates/me/application/sections/achievements_activities", {
        method: "PATCH",
        json: buildPayload(values),
      });
      bustApiCache("/candidates/me");
      setMsg("Черновик сохранен.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить черновик");
    }
  }

  async function onSubmit(data: Form) {
    setMsg(null);
    try {
      await apiFetch("/candidates/me/application/sections/achievements_activities", {
        method: "PATCH",
        json: buildPayload(data),
      });
      bustApiCache("/candidates/me");
      clearDraft("achievements");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  const textValue = watch("achievements_text") ?? "";
  const charCount = textValue.length;

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      {/* Section header */}
      <div className={styles.sectionHeader}>
        <p className={styles.sectionTitle}>Ваши достижения</p>
        <p className={styles.sectionDesc}>
          Опишите самые важные достижения, проекта или инициативы. Напишите, что это было, что сделали именно вы и почему это для вас важно
        </p>
      </div>

      <Divider />

      {/* Main textarea block */}
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <p className={styles.blockTitle}>Опишите самые важные достижения, проекты или инициативы</p>

        <textarea
          className={styles.textarea}
          placeholder="Напишите ответ"
          maxLength={500}
          {...register("achievements_text")}
        />

        <div className={styles.counterRow}>
          <span className={styles.counter}>{charCount}/500 символов</span>
          <span className={styles.counterHint}>Минимум 250</span>
        </div>

        {errors.achievements_text && (
          <p className="error" style={{ margin: 0 }}>
            {errors.achievements_text.message}
          </p>
        )}

        {/* Role + Year row */}
        <div className={styles.roleYearRow}>
          <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            <label className={styles.fieldLabel}>Ваша роль</label>
            <input
              className={styles.fieldInput}
              placeholder="Например: Координатор"
              maxLength={50}
              {...register("role")}
            />
            {errors.role && (
              <p className="error" style={{ margin: 0 }}>{errors.role.message}</p>
            )}
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 11 }}>
            <label className={styles.fieldLabel}>Год</label>
            <input
              className={styles.fieldInput}
              placeholder="Год достижения: 2025"
              maxLength={4}
              inputMode="numeric"
              {...register("year")}
              onKeyDown={(e) => {
                if (
                  e.key.length === 1 &&
                  !/\d/.test(e.key) &&
                  !e.ctrlKey &&
                  !e.metaKey
                ) {
                  e.preventDefault();
                }
              }}
            />
            {errors.year && (
              <p className="error" style={{ margin: 0 }}>{errors.year.message}</p>
            )}
          </div>
        </div>
      </div>

      <Divider />

      {/* Links section */}
      <div style={{ display: "flex", flexDirection: "column", gap: 8, marginBottom: 24 }}>
        <p className={styles.sectionTitle}>Ссылки на проекты</p>
        <p className={styles.sectionDesc}>
          Если у вас есть материалы, которые помогают лучше понять ваши достижения, добавьте ссылки. Это может быть GitHub, Behance, личный сайт, Figma, Google Drive, YouTube или другой ресурс
        </p>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        {fields.map((field, idx) => {
          const isDynamic = idx >= STATIC_LINKS.length;
          return (
            <div key={field.id} className={styles.linkField}>
              <p className={styles.linkLabel}>{field.label}</p>
              <div className={styles.linkInputRow}>
                <input
                  className={styles.fieldInput}
                  placeholder="Вставьте ссылку"
                  {...register(`links.${idx}.url`)}
                />
                {isDynamic && (
                  <button
                    type="button"
                    className={styles.deleteLinkBtn}
                    onClick={() => remove(idx)}
                    aria-label="Удалить ссылку"
                  >
                    ✕
                  </button>
                )}
              </div>
              {errors.links?.[idx]?.url && (
                <p className="error" style={{ margin: 0 }}>
                  {errors.links[idx]!.url!.message}
                </p>
              )}
            </div>
          );
        })}

        {fields.length < MAX_TOTAL_LINKS && (
          <button
            type="button"
            className={styles.addLinkBtn}
            onClick={() =>
              append({ link_type: "extra", label: "Дополнительно", url: "" })
            }
          >
            <svg className={styles.addLinkIcon} viewBox="0 0 14 14" fill="none">
              <path
                d="M7 1V13M1 7H13"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
            Добавить ссылку
          </button>
        )}
      </div>

      <Divider />

      {/* Consents */}
      <div className={formStyles.consentBlock}>
        <Controller
          name="consent_privacy"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Отправляя эту форму, вы соглашаетесь на обработку ваших персональных данных в соответствии с нашей{" "}
              <Link href="/privacy">Политикой конфиденциальности</Link>
            </ConsentCheckbox>
          )}
        />
        {errors.consent_privacy && (
          <p className="error" style={{ margin: 0 }}>{errors.consent_privacy.message}</p>
        )}
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
        {errors.consent_parent && (
          <p className="error" style={{ margin: 0 }}>{errors.consent_parent.message}</p>
        )}
      </div>

      <Divider />

      {msg && (
        <p className={msg.includes("Не удалось") || msg.includes("Заполните") ? "error" : "muted"} role="alert">
          {msg}
        </p>
      )}

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
