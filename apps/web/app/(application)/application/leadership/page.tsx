"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, useFieldArray } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError, apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import formStyles from "@/components/application/form-ui.module.css";

const leadershipItemSchema = z.object({
  title: z.string().min(1, "Обязательное поле").max(255),
  scope: z.string().max(500).optional().or(z.literal("")),
  outcome: z.string().max(2000).optional().or(z.literal("")),
});

const schema = z.object({
  items: z.array(leadershipItemSchema).min(1, "Добавьте хотя бы один пример").max(20),
});

type Form = z.infer<typeof schema>;

const EMPTY_ITEM: Form["items"][number] = {
  title: "",
  scope: "",
  outcome: "",
};

export default function LeadershipPage() {
  const [msg, setMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { items: [EMPTY_ITEM] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "items" });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          sections: Record<string, { payload: unknown }>;
        }>("/candidates/me/application", 2 * 60 * 1000);
        const raw = app.sections.leadership_evidence?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        const items = Array.isArray(raw.items) ? raw.items : [];
        if (items.length > 0) {
          reset({ items: items as Form["items"] });
        }
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        setMsg("Не удалось загрузить данные. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    setMsg(null);
    const payload = {
      items: data.items.map((item) => ({
        title: item.title,
        scope: item.scope || undefined,
        outcome: item.outcome || undefined,
      })),
    };
    try {
      await apiFetch("/candidates/me/application/sections/leadership_evidence", {
        method: "PATCH",
        json: { payload },
      });
      bustApiCache("/candidates/me");
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <FormSection title="Лидерский опыт">
        {fields.map((field, idx) => (
          <div key={field.id} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {idx > 0 && <Divider />}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h3 className={formStyles.label} style={{ fontSize: 16, fontWeight: 500 }}>
                Пример {idx + 1}
              </h3>
              {fields.length > 1 && (
                <button type="button" className="btn secondary" style={{ fontSize: 13 }} onClick={() => remove(idx)}>
                  Удалить
                </button>
              )}
            </div>

            <div className={formStyles.field}>
              <label className={formStyles.label}>Название *</label>
              <input className={formStyles.input} {...register(`items.${idx}.title`)} placeholder="Название инициативы или проекта" />
              {errors.items?.[idx]?.title && (
                <p className="error" style={{ margin: "4px 0 0" }}>{errors.items[idx]!.title!.message}</p>
              )}
            </div>

            <div className={formStyles.field}>
              <label className={formStyles.label}>Масштаб</label>
              <textarea
                className={formStyles.input}
                style={{ minHeight: 60, resize: "vertical", padding: "10px 16px" }}
                maxLength={500}
                {...register(`items.${idx}.scope`)}
                placeholder="Опишите масштаб: кол-во участников, география и т.д."
              />
            </div>

            <div className={formStyles.field}>
              <label className={formStyles.label}>Результат</label>
              <textarea
                className={formStyles.input}
                style={{ minHeight: 80, resize: "vertical", padding: "10px 16px" }}
                maxLength={2000}
                {...register(`items.${idx}.outcome`)}
                placeholder="Опишите результаты и достижения"
              />
            </div>
          </div>
        ))}

        {errors.items?.root && (
          <p className="error" style={{ margin: 0 }}>{errors.items.root.message}</p>
        )}

        {fields.length < 20 && (
          <button type="button" className="btn secondary" onClick={() => append(EMPTY_ITEM)}>
            + Добавить пример
          </button>
        )}
      </FormSection>

      <Divider />

      {msg && <p className={msg.includes("Не удалось") ? "error" : "muted"} role="alert">{msg}</p>}

      <div className={formStyles.formFooter}>
        <button className="btn secondary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Сохранить"}
        </button>
        <Link className="btn" href="/application/motivation">
          Далее
        </Link>
      </div>
    </form>
  );
}
