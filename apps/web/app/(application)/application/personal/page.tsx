"use client";

import Link from "next/link";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch } from "@/lib/api-client";
import { personalSchema } from "@/lib/validation";
import { z } from "zod";

type Form = z.infer<typeof personalSchema>;

export default function PersonalPage() {
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(personalSchema) });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetch<{ sections: Record<string, { payload: unknown }> }>("/candidates/me/application");
        const p = app.sections.personal?.payload as Form | undefined;
        if (p) {
          reset(p);
        }
      } catch {
        /* ignore */
      }
    }
    void load();
  }, [reset]);

  async function onSubmit(data: Form) {
    await apiFetch("/candidates/me/application/sections/personal", {
      method: "PATCH",
      json: { payload: data },
    });
  }

  return (
    <form className="card grid" style={{ maxWidth: 560 }} onSubmit={handleSubmit(onSubmit)}>
      <h1 className="h1" style={{ fontSize: 20 }}>
        Личные данные
      </h1>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
        <div>
          <label className="label">Имя (как в заявлении)</label>
          <input className="input" {...register("preferred_first_name")} />
          {errors.preferred_first_name && <div className="error">{errors.preferred_first_name.message}</div>}
        </div>
        <div>
          <label className="label">Фамилия</label>
          <input className="input" {...register("preferred_last_name")} />
          {errors.preferred_last_name && <div className="error">{errors.preferred_last_name.message}</div>}
        </div>
      </div>
      <div>
        <label className="label">Дата рождения (необязательно)</label>
        <input className="input" type="date" {...register("date_of_birth")} />
      </div>
      <div>
        <label className="label">Местоимения (необязательно)</label>
        <input className="input" {...register("pronouns")} />
      </div>
      <div style={{ display: "flex", gap: 10 }}>
        <button className="btn" type="submit" disabled={isSubmitting}>
          Сохранить
        </button>
        <Link className="btn secondary" href="/application/contact">
          Далее
        </Link>
      </div>
    </form>
  );
}
