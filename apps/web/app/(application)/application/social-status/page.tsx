"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch } from "@/lib/api-client";
import { socialSchema } from "@/lib/validation";
import { z } from "zod";

type Form = z.infer<typeof socialSchema>;

export default function SocialStatusPage() {
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [fileMsg, setFileMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(socialSchema) });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetch<{ application: { id: string }; sections: Record<string, { payload: unknown }> }>(
          "/candidates/me/application",
        );
        setApplicationId(app.application.id);
        const p = app.sections.social_status_cert?.payload as Form | undefined;
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
      await apiFetch("/candidates/me/application/sections/social_status_cert", {
        method: "PATCH",
        json: { payload: data },
      });
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function upload(file: File | null) {
    setFileMsg(null);
    if (!file || !applicationId) {
      setFileMsg("Выберите файл и дождитесь загрузки заявления.");
      return;
    }
    const fd = new FormData();
    fd.append("application_id", applicationId);
    fd.append("document_type", "certificate_of_social_status");
    fd.append("file", file);
    try {
      const base = typeof window === "undefined" ? "" : "";
      const url = `${base}/api/v1/documents/upload`;
      const res = await fetch(url, { method: "POST", body: fd, credentials: "include" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok) {
        setFileMsg(JSON.stringify(data));
        return;
      }
      setFileMsg(`Загружено: ${data.original_filename}`);
    } catch (e) {
      setFileMsg(e instanceof Error ? e.message : "Ошибка загрузки");
    }
  }

  return (
    <div className="grid" style={{ maxWidth: 640, gap: 16 }}>
      <form className="card grid" onSubmit={handleSubmit(onSubmit)}>
        <h1 className="h1" style={{ fontSize: 20 }}>
          Справка о социальном статусе
        </h1>
        <p className="muted" style={{ margin: 0 }}>
          Загрузите официальную справку (PDF или изображение) и подтвердите достоверность ниже.
        </p>
        <div>
          <label className="label">Подтверждение</label>
          <textarea className="input" rows={6} {...register("attestation")} />
          {errors.attestation && <div className="error">{errors.attestation.message}</div>}
        </div>
        {msg && <div className="muted">{msg}</div>}
        <button className="btn" type="submit" disabled={isSubmitting}>
          Сохранить
        </button>
      </form>

      <div className="card grid">
        <h2 className="h2">Загрузка справки</h2>
        <input
          type="file"
          accept="application/pdf,image/png,image/jpeg"
          onChange={(e) => void upload(e.target.files?.[0] || null)}
        />
        {fileMsg && <div className="muted">{fileMsg}</div>}
      </div>

      <Link className="btn secondary" href="/application/review" style={{ alignSelf: "flex-start" }}>
        Далее: проверка
      </Link>
    </div>
  );
}
