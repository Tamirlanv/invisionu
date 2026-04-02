"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { ApiError, apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import formStyles from "@/components/application/form-ui.module.css";

const schema = z.object({
  acknowledged_required_documents: z.boolean(),
  notes: z.string().max(2000).optional().or(z.literal("")),
});

type Form = z.infer<typeof schema>;

const REQUIRED_DOCUMENTS = [
  "Удостоверение личности (паспорт / ID-карта)",
  "Аттестат или табель успеваемости",
  "Сертификат по английскому языку (IELTS / TOEFL)",
  "Справка о социальном статусе (при наличии)",
  "Фотография 3×4",
];

export default function DocumentsPage() {
  const [msg, setMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    formState: { isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(schema),
    defaultValues: { acknowledged_required_documents: false, notes: "" },
  });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          sections: Record<string, { payload: unknown }>;
        }>("/candidates/me/application", 2 * 60 * 1000);
        const raw = app.sections.documents_manifest?.payload as Record<string, unknown> | undefined;
        if (!raw) return;
        reset({
          acknowledged_required_documents: Boolean(raw.acknowledged_required_documents),
          notes: raw.notes != null ? String(raw.notes) : "",
        });
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
      acknowledged_required_documents: data.acknowledged_required_documents,
      notes: data.notes || undefined,
    };
    try {
      await apiFetch("/candidates/me/application/sections/documents_manifest", {
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
      <FormSection title="Документы">
        <p className="muted" style={{ margin: 0 }}>
          Пожалуйста, убедитесь, что у вас есть следующие документы. Они потребуются на следующих этапах.
        </p>

        <ul style={{ margin: 0, paddingLeft: 20, display: "flex", flexDirection: "column", gap: 8 }}>
          {REQUIRED_DOCUMENTS.map((doc) => (
            <li key={doc} style={{ fontSize: 14, color: "#262626" }}>{doc}</li>
          ))}
        </ul>

        <Controller
          name="acknowledged_required_documents"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Я ознакомился(-ась) со списком необходимых документов и подготовлю их к подаче
            </ConsentCheckbox>
          )}
        />
      </FormSection>

      <Divider />

      <FormSection title="Примечания">
        <div className={formStyles.field}>
          <label className={formStyles.label}>Дополнительные заметки</label>
          <textarea
            className={formStyles.input}
            style={{ minHeight: 100, resize: "vertical", padding: "10px 16px" }}
            maxLength={2000}
            {...register("notes")}
            placeholder="Укажите дополнительную информацию, если необходимо"
          />
        </div>
      </FormSection>

      <Divider />

      {msg && <p className={msg.includes("Не удалось") ? "error" : "muted"} role="alert">{msg}</p>}

      <div className={formStyles.formFooter}>
        <button className="btn secondary" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Сохранение…" : "Сохранить"}
        </button>
        <Link className="btn" href="/application/social-status">
          Далее
        </Link>
      </div>
    </form>
  );
}
