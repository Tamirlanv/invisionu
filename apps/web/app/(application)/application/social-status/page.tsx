"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch, apiFetchCached, ApiError, bustApiCache, uploadDocumentForm } from "@/lib/api-client";
import { socialSchema } from "@/lib/validation";
import { FileUploadField, type UploadedFileDisplay } from "@/components/application/FileUploadField";
import { z } from "zod";

type Form = z.infer<typeof socialSchema>;

export default function SocialStatusPage() {
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [fileMsg, setFileMsg] = useState<string | null>(null);
  const [uploadedCert, setUploadedCert] = useState<UploadedFileDisplay | null>(null);
  const [certUploading, setCertUploading] = useState(false);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(socialSchema) });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          application: { id: string };
          sections: Record<string, { payload: unknown }>;
          documents?: { id: string; document_type: string; original_filename: string; byte_size: number }[];
        }>("/candidates/me/application", 2 * 60 * 1000);
        setApplicationId(app.application.id);
        const p = app.sections.social_status_cert?.payload as Form | undefined;
        if (p) reset(p);
        const docs = app.documents?.filter((d) => d.document_type === "certificate_of_social_status") ?? [];
        const last = docs[docs.length - 1];
        if (last) {
          setUploadedCert({ name: last.original_filename, sizeBytes: last.byte_size });
        } else {
          setUploadedCert(null);
        }
      } catch {
        setFileMsg("Не удалось загрузить данные заявления. Обновите страницу.");
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
      bustApiCache("/candidates/me");
      setMsg("Сохранено.");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  async function onCertFile(file: File | null) {
    setFileMsg(null);
    if (!file) return;
    if (!applicationId) {
      setFileMsg("Выберите файл после загрузки заявления.");
      return;
    }
    const rollback = uploadedCert;
    setUploadedCert({ name: file.name, sizeBytes: file.size });
    setCertUploading(true);
    setFileMsg(null);

    const fd = new FormData();
    fd.append("application_id", applicationId);
    fd.append("document_type", "certificate_of_social_status");
    fd.append("file", file);
    try {
      const data = await uploadDocumentForm<{
        original_filename?: string;
        byte_size?: number;
      }>(fd);
      bustApiCache("/candidates/me");
      setUploadedCert({
        name: data.original_filename ?? file.name,
        sizeBytes: data.byte_size ?? file.size,
      });
      setFileMsg(null);
    } catch (e) {
      setUploadedCert(rollback);
      setFileMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Ошибка загрузки");
    } finally {
      setCertUploading(false);
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
        {fileMsg ? (
          <p className="error" role="alert" style={{ margin: 0 }}>
            {fileMsg}
          </p>
        ) : null}
        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={uploadedCert}
          isUploading={certUploading}
          allowRemove={false}
          onFile={(f) => void onCertFile(f)}
        />
      </div>

      <Link className="btn" href="/application/review" style={{ alignSelf: "flex-start" }}>
        Далее: проверка
      </Link>
    </div>
  );
}
