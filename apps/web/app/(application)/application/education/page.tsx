"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch } from "@/lib/api-client";
import { educationSchema } from "@/lib/validation";
import { z } from "zod";

type Form = z.infer<typeof educationSchema>;

export default function EducationPage() {
  const [msg, setMsg] = useState<string | null>(null);
  const {
    register,
    control,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(educationSchema),
    defaultValues: { entries: [{ institution_name: "", is_current: false }] },
  });

  const { fields, append, remove } = useFieldArray({ control, name: "entries" });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetch<{
          sections: Record<string, { payload: unknown }>;
          education_records: {
            institution_name: string;
            degree_or_program?: string | null;
            field_of_study?: string | null;
            start_date?: string | null;
            end_date?: string | null;
            is_current: boolean;
          }[];
        }>("/candidates/me/application");
        const p = app.sections.education?.payload as Form | undefined;
        if (p?.entries?.length) {
          reset(p);
        } else if (app.education_records.length) {
          reset({
            entries: app.education_records.map((e) => ({
              institution_name: e.institution_name,
              degree_or_program: e.degree_or_program || "",
              field_of_study: e.field_of_study || "",
              start_date: e.start_date ? e.start_date.slice(0, 10) : "",
              end_date: e.end_date ? e.end_date.slice(0, 10) : "",
              is_current: e.is_current,
            })),
          });
        }
      } catch {
        /* ignore */
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    setMsg(null);
    try {
      const cleaned = {
        ...data,
        entries: data.entries.map((e) => ({
          ...e,
          start_date: e.start_date || undefined,
          end_date: e.end_date || undefined,
          degree_or_program: e.degree_or_program || undefined,
          field_of_study: e.field_of_study || undefined,
        })),
      };
      await apiFetch("/candidates/me/application/sections/education", {
        method: "PATCH",
        json: { payload: cleaned },
      });
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form className="card grid" style={{ maxWidth: 640 }} onSubmit={handleSubmit(onSubmit)}>
      <h1 className="h1" style={{ fontSize: 20 }}>
        Образование
      </h1>
      {fields.map((field, index) => (
        <div key={field.id} className="card grid" style={{ background: "rgba(0,0,0,0.2)" }}>
          <div>
            <label className="label">Учебное заведение</label>
            <input className="input" {...register(`entries.${index}.institution_name` as const)} />
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label className="label">Степень / программа</label>
              <input className="input" {...register(`entries.${index}.degree_or_program` as const)} />
            </div>
            <div>
              <label className="label">Направление / специальность</label>
              <input className="input" {...register(`entries.${index}.field_of_study` as const)} />
            </div>
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <label className="label">Начало</label>
              <input className="input" type="date" {...register(`entries.${index}.start_date` as const)} />
            </div>
            <div>
              <label className="label">Окончание</label>
              <input className="input" type="date" {...register(`entries.${index}.end_date` as const)} />
            </div>
          </div>
          <label style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <input type="checkbox" {...register(`entries.${index}.is_current` as const)} />
            Учусь сейчас
          </label>
          {fields.length > 1 && (
            <button className="btn secondary" type="button" onClick={() => remove(index)}>
              Удалить
            </button>
          )}
        </div>
      ))}
      {errors.entries && <div className="error">{errors.entries.message}</div>}
      <button className="btn secondary" type="button" onClick={() => append({ institution_name: "", is_current: false })}>
        Добавить учебное заведение
      </button>
      {msg && <div className="muted">{msg}</div>}
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn" type="submit" disabled={isSubmitting}>
          Сохранить
        </button>
        <Link className="btn secondary" href="/application/internal-test">
          Далее
        </Link>
      </div>
    </form>
  );
}
