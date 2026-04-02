"use client";

import Image from "next/image";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller, useWatch } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch, apiFetchCached, ApiError, bustApiCache, uploadDocumentForm } from "@/lib/api-client";
import { educationSchema } from "@/lib/validation";
import { FormSection } from "@/components/application/FormSection";
import { Divider } from "@/components/application/Divider";
import { FileUploadField, type UploadedFileDisplay } from "@/components/application/FileUploadField";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { PresentationInstructionModal } from "@/components/application/PresentationInstructionModal";
import { useLinkCheck } from "@/lib/hooks/useLinkCheck";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import formStyles from "@/components/application/form-ui.module.css";
import eduStyles from "./education.module.css";
import { z } from "zod";

type Form = z.infer<typeof educationSchema>;

const DEFAULTS: Partial<Form> = {
  entries: [],
  presentation_video_url: "",
  english_proof_kind: "ielts_6",
  certificate_proof_kind: "ent",
  consent_privacy: false,
  consent_parent: false,
};

function isUuid(s: string | undefined): s is string {
  return !!s && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s);
}

type DocRow = { id: string; document_type: string; original_filename: string; byte_size: number };

function docMetaForId(docs: DocRow[], docId: string | undefined): UploadedFileDisplay | null {
  if (!docId) return null;
  const d = docs.find((x) => x.id === docId);
  return d ? { name: d.original_filename, sizeBytes: d.byte_size } : null;
}

type FileKind = "english" | "certificate" | "additional";

export default function EducationPage() {
  const router = useRouter();
  const [instructionOpen, setInstructionOpen] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [fileMeta, setFileMeta] = useState<{
    english: UploadedFileDisplay | null;
    certificate: UploadedFileDisplay | null;
    additional: UploadedFileDisplay | null;
  }>({
    english: null,
    certificate: null,
    additional: null,
  });
  const [uploadingKind, setUploadingKind] = useState<FileKind | null>(null);

  const {
    register,
    handleSubmit,
    reset,
    control,
    setValue,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Form>({

    resolver: zodResolver(educationSchema),
    defaultValues: DEFAULTS as Form,
  });

  const videoUrl = useWatch({ control, name: "presentation_video_url" });
  const linkCheck = useLinkCheck(videoUrl);

  const uploadDocument = useCallback(
    async (file: File | null, documentType: string, kind: FileKind) => {
      const field =
        kind === "english"
          ? "english_document_id"
          : kind === "certificate"
            ? "certificate_document_id"
            : "additional_document_id";

      if (!file) {
        if (!applicationId) return;
        try {
          const v = getValues();
          const payload = {
            entries: v.entries.map((e) => ({
              ...e,
              start_date: e.start_date || undefined,
              end_date: e.end_date || undefined,
              degree_or_program: e.degree_or_program || undefined,
              field_of_study: e.field_of_study || undefined,
            })),
            presentation_video_url: v.presentation_video_url.trim(),
            english_proof_kind: v.english_proof_kind,
            certificate_proof_kind: v.certificate_proof_kind,
            english_document_id:
              kind === "english"
                ? null
                : isUuid(v.english_document_id)
                  ? v.english_document_id
                  : null,
            certificate_document_id:
              kind === "certificate"
                ? null
                : isUuid(v.certificate_document_id)
                  ? v.certificate_document_id
                  : null,
            additional_document_id:
              kind === "additional"
                ? null
                : isUuid(v.additional_document_id)
                  ? v.additional_document_id
                  : null,
          };
          await apiFetch("/candidates/me/application/sections/education", {
            method: "PATCH",
            json: { payload },
          });
          setValue(field, undefined, { shouldValidate: true, shouldDirty: true });
          setFileMeta((prev) => ({ ...prev, [kind]: null }));
          bustApiCache("/candidates/me");
          setMsg(null);
        } catch (e) {
          setMsg(e instanceof Error ? e.message : "Не удалось удалить файл");
        }
        return;
      }

      if (!applicationId) {
        setMsg("Не удалось определить заявление. Обновите страницу.");
        return;
      }

      const rollback = fileMeta[kind];
      setFileMeta((prev) => ({
        ...prev,
        [kind]: { name: file.name, sizeBytes: file.size },
      }));
      setUploadingKind(kind);
      setMsg(null);

      const fd = new FormData();
      fd.append("application_id", applicationId);
      fd.append("document_type", documentType);
      fd.append("file", file);
      try {
        const data = await uploadDocumentForm<{
          id: string;
          original_filename?: string;
          byte_size?: number;
        }>(fd);
        setValue(field, data.id, { shouldValidate: true, shouldDirty: true });
        setFileMeta((prev) => ({
          ...prev,
          [kind]: {
            name: data.original_filename ?? file.name,
            sizeBytes: data.byte_size ?? file.size,
          },
        }));
        bustApiCache("/candidates/me");
        setMsg(null);
      } catch (e) {
        setFileMeta((prev) => ({ ...prev, [kind]: rollback }));
        setMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось загрузить файл");
      } finally {
        setUploadingKind((prev) => (prev === kind ? null : prev));
      }
    },
    [applicationId, fileMeta, getValues, setValue],
  );

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          application: { id: string };
          sections: Record<string, { payload: unknown }>;
          documents?: DocRow[];
          education_records: {
            institution_name: string;
            degree_or_program?: string | null;
            field_of_study?: string | null;
            start_date?: string | null;
            end_date?: string | null;
            is_current: boolean;
          }[];
        }>("/candidates/me/application", 2 * 60 * 1000);
        setApplicationId(app.application.id);
        const docs = app.documents ?? [];

        const raw = app.sections.education?.payload as Record<string, unknown> | undefined;
        const entriesFromRecords =
          app.education_records?.map((e) => ({
            institution_name: e.institution_name,
            degree_or_program: e.degree_or_program || "",
            field_of_study: e.field_of_study || "",
            start_date: e.start_date ? e.start_date.slice(0, 10) : "",
            end_date: e.end_date ? e.end_date.slice(0, 10) : "",
            is_current: e.is_current,
          })) ?? [];

        let apiValues: Partial<Form> = {};
        if (raw) {
          const entriesPayload = Array.isArray(raw.entries) ? raw.entries : [];
          const entries =
            entriesPayload.length > 0
              ? (entriesPayload as Form["entries"])
              : entriesFromRecords.length > 0
                ? entriesFromRecords
                : [];
          apiValues = {
            entries,
            presentation_video_url: raw.presentation_video_url != null ? String(raw.presentation_video_url) : "",
            english_proof_kind:
              raw.english_proof_kind === "toefl_60_78" ? "toefl_60_78" : "ielts_6",
            certificate_proof_kind: raw.certificate_proof_kind === "nis_12" ? "nis_12" : "ent",
            english_document_id: raw.english_document_id != null ? String(raw.english_document_id) : undefined,
            certificate_document_id:
              raw.certificate_document_id != null ? String(raw.certificate_document_id) : undefined,
            additional_document_id:
              raw.additional_document_id != null ? String(raw.additional_document_id) : undefined,
            consent_privacy: Boolean(raw.consent_privacy),
            consent_parent: Boolean(raw.consent_parent),
          };
        } else if (entriesFromRecords.length) {
          apiValues = { entries: entriesFromRecords };
        }

        const local = loadDraft<Form>("education");
        const merged = { ...DEFAULTS, ...apiValues, ...local } as Form;
        reset(merged);

        const engId = merged.english_document_id;
        const certId = merged.certificate_document_id;
        const addId = merged.additional_document_id;
        setFileMeta({
          english: docMetaForId(docs, engId),
          certificate: docMetaForId(docs, certId),
          additional: docMetaForId(docs, addId),
        });
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        setMsg("Не удалось загрузить данные заявления. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  useEffect(() => {
    const sub = watch((_, { name }) => {
      if (name === "consent_privacy" || name === "consent_parent") {
        saveDraftLocal("education", getValues());
      }
    });
    return () => sub.unsubscribe();
  }, [watch, getValues]);

  function buildPayload(data: Form) {
    return {
      entries: data.entries.map((e) => ({
        ...e,
        start_date: e.start_date || undefined,
        end_date: e.end_date || undefined,
        degree_or_program: e.degree_or_program || undefined,
        field_of_study: e.field_of_study || undefined,
      })),
      presentation_video_url: data.presentation_video_url.trim(),
      english_proof_kind: data.english_proof_kind,
      certificate_proof_kind: data.certificate_proof_kind,
      english_document_id: isUuid(data.english_document_id) ? data.english_document_id : undefined,
      certificate_document_id: isUuid(data.certificate_document_id) ? data.certificate_document_id : undefined,
      additional_document_id: isUuid(data.additional_document_id) ? data.additional_document_id : undefined,
      consent_privacy: data.consent_privacy,
      consent_parent: data.consent_parent,
    };
  }

  async function saveDraft() {
    setMsg(null);
    const values = getValues();
    saveDraftLocal("education", values);
    try {
      await apiFetch("/candidates/me/application/sections/education", {
        method: "PATCH",
        json: { payload: buildPayload(values) },
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
      await apiFetch("/candidates/me/application/sections/education", {
        method: "PATCH",
        json: { payload: buildPayload(data) },
      });
      bustApiCache("/candidates/me");
      clearDraft("education");
      router.push("/application/internal-test");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <>
      <PresentationInstructionModal open={instructionOpen} onClose={() => setInstructionOpen(false)} />
      <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <h1 className="h1" style={{ fontSize: 20, marginBottom: 24 }}>
        Образование
      </h1>

      <FormSection title="Персональная презентация">
        <div className={formStyles.field} style={{ width: "100%" }}>
          <label className={formStyles.label}>Ссылка на презентацию</label>
          <input
            className={formStyles.input}
            type="text"
            inputMode="url"
            autoComplete="url"
            placeholder="Вставьте ссылку"
            {...register("presentation_video_url")}
          />
          {errors.presentation_video_url && (
            <p className="error" style={{ margin: "8px 0 0 0" }}>
              {errors.presentation_video_url.message}
            </p>
          )}
          {linkCheck.statusMessage && (
            <p
              style={{
                margin: "8px 0 0 0",
                fontSize: 13,
                color:
                  linkCheck.status === "checking"
                    ? "var(--text-secondary, #888)"
                    : linkCheck.status === "reachable"
                      ? "var(--success, #2e7d32)"
                      : "var(--warning, #e65100)",
              }}
            >
              {linkCheck.statusMessage}
            </p>
          )}
        </div>

        <div className={eduStyles.instructionRow}>
          <div className={eduStyles.instructionText}>
            <p>Пожалуйста, пришлите ссылку на вашу видеопрезентацию.</p>
            <p>Более подробную информацию о том, как создать видео, см. в инструкциях.</p>
          </div>
          <button
            type="button"
            className={`btn ${eduStyles.instructionBtn}`}
            onClick={() => setInstructionOpen(true)}
            aria-haspopup="dialog"
          >
            <Image
              src="/assets/icons/codex_file.svg"
              alt=""
              width={14}
              height={14}
              className={eduStyles.instructionBtnIcon}
              unoptimized
              aria-hidden
            />
            Инструкция
          </button>
        </div>
      </FormSection>

      <Divider />

      <FormSection title="Английский язык">
        <div className={formStyles.field}>
          <span className={formStyles.label}>Вид подтверждения</span>
          <Controller
            name="english_proof_kind"
            control={control}
            render={({ field }) => (
              <PillSegmentedControl
                aria-label="Вид подтверждения по английскому"
                options={[
                  { value: "ielts_6", label: "IELTS 6.0" },
                  { value: "toefl_60_78", label: "TOEFL iBT 60-78" },
                ]}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>

        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={fileMeta.english}
          isUploading={uploadingKind === "english"}
          onFile={(f) => void uploadDocument(f, "supporting_documents", "english")}
        />
        {errors.english_document_id && (
          <p className="error" style={{ margin: 0 }}>{errors.english_document_id.message}</p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Сертификат">
        <div className={formStyles.field}>
          <span className={formStyles.label}>Вид подтверждения</span>
          <Controller
            name="certificate_proof_kind"
            control={control}
            render={({ field }) => (
              <PillSegmentedControl
                aria-label="Вид подтверждения сертификата"
                options={[
                  { value: "ent", label: "ЕНТ" },
                  { value: "nis_12", label: "НИШ 12 классов" },
                ]}
                value={field.value}
                onChange={field.onChange}
              />
            )}
          />
        </div>

        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={fileMeta.certificate}
          isUploading={uploadingKind === "certificate"}
          onFile={(f) => void uploadDocument(f, "supporting_documents", "certificate")}
        />
        {errors.certificate_document_id && (
          <p className="error" style={{ margin: 0 }}>{errors.certificate_document_id.message}</p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Дополнительные документы">
        <p className="muted" style={{ margin: 0, fontSize: 14, maxWidth: 560 }}>
          Если у вас есть дополнительная информация о вашем образовании, вы можете загрузить её здесь.
        </p>

        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={fileMeta.additional}
          isUploading={uploadingKind === "additional"}
          onFile={(f) => void uploadDocument(f, "supporting_documents", "additional")}
        />
      </FormSection>

      <Divider />

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
          <p className="error" style={{ margin: 0 }}>
            {errors.consent_privacy.message}
          </p>
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
          <p className="error" style={{ margin: 0 }}>
            {errors.consent_parent.message}
          </p>
        )}
      </div>

      <Divider />

      {msg && (
        <p className={msg.includes("Не удалось") ? "error" : "muted"} role="status">{msg}</p>
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
    </>
  );
}
