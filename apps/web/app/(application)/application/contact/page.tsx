"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch } from "@/lib/api-client";
import { contactSchema } from "@/lib/validation";
import { z } from "zod";

type Form = z.infer<typeof contactSchema>;

export default function ContactPage() {
  const [msg, setMsg] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(contactSchema) });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetch<{ sections: Record<string, { payload: unknown }> }>("/candidates/me/application");
        const p = app.sections.contact?.payload as Form | undefined;
        if (p) reset(p);
      } catch {
        /* ignore */
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    setMsg(null);
    try {
      await apiFetch("/candidates/me/application/sections/contact", {
        method: "PATCH",
        json: { payload: data },
      });
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form className="card grid" style={{ maxWidth: 560 }} onSubmit={handleSubmit(onSubmit)}>
      <h1 className="h1" style={{ fontSize: 20 }}>
        Контакты
      </h1>
      <div>
        <label className="label">Телефон (E.164)</label>
        <input className="input" placeholder="+77001234567" {...register("phone_e164")} />
        {errors.phone_e164 && <div className="error">{errors.phone_e164.message}</div>}
      </div>
      <div>
        <label className="label">Адрес, строка 1</label>
        <input className="input" {...register("address_line1")} />
      </div>
      <div>
        <label className="label">Адрес, строка 2</label>
        <input className="input" {...register("address_line2")} />
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label">Город</label>
          <input className="input" {...register("city")} />
        </div>
        <div>
          <label className="label">Регион / область</label>
          <input className="input" {...register("region")} />
        </div>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label">Почтовый индекс</label>
          <input className="input" {...register("postal_code")} />
        </div>
        <div>
          <label className="label">Страна (ISO-2)</label>
          <input className="input" {...register("country")} />
          {errors.country && <div className="error">{errors.country.message}</div>}
        </div>
      </div>
      {msg && <div className="muted">{msg}</div>}
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn" type="submit" disabled={isSubmitting}>
          Сохранить
        </button>
        <Link className="btn secondary" href="/application/education">
          Далее
        </Link>
      </div>
    </form>
  );
}
