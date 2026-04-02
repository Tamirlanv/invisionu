"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, apiFetchCached, ApiError, bustApiCache, uploadDocumentForm } from "@/lib/api-client";
import { personalSchema } from "@/lib/validation";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { FormSection } from "@/components/application/FormSection";
import { FormField } from "@/components/application/FormField";
import { Divider } from "@/components/application/Divider";
import { SelectField } from "@/components/application/SelectField";
import { FileUploadField, type UploadedFileDisplay } from "@/components/application/FileUploadField";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import formStyles from "@/components/application/form-ui.module.css";

const personalFormSchema = personalSchema.extend({
  middle_name: z.string().optional(),
  date_of_birth: z.string().min(1, { message: "Укажите дату рождения" }),
  gender: z.enum(["male", "female"], { required_error: "Укажите пол" }),
  document_type: z.enum(["id", "passport"], { required_error: "Выберите тип документа" }),
  citizenship: z.string().min(1, { message: "Укажите гражданство" }),
  iin: z.string().min(1, { message: "Укажите ИИН" }),
  document_number: z.string().min(1, { message: "Укажите номер документа" }),
  document_issue_date: z.string().min(1, { message: "Укажите дату выдачи" }),
  document_issued_by: z.string().min(1, { message: "Укажите кем выдан" }),
  father_last: z.string().min(1, { message: "Укажите фамилию отца" }),
  father_first: z.string().min(1, { message: "Укажите имя отца" }),
  father_middle: z.string().optional(),
  father_phone: z.string().min(1, { message: "Укажите телефон отца" }),
  mother_last: z.string().min(1, { message: "Укажите фамилию матери" }),
  mother_first: z.string().min(1, { message: "Укажите имя матери" }),
  mother_middle: z.string().optional(),
  mother_phone: z.string().min(1, { message: "Укажите телефон матери" }),
  guardian_last: z.string().optional(),
  guardian_first: z.string().optional(),
  guardian_middle: z.string().optional(),
  guardian_phone: z.string().optional(),
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_age: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
  identity_document_id: z.string().min(1, { message: "Загрузите документ" }),
});

type PersonalForm = z.infer<typeof personalFormSchema>;

type DocRow = { id: string; document_type: string; original_filename: string; byte_size: number };

function isUuid(s: string | undefined): s is string {
  return !!s && /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i.test(s);
}

function docMetaForId(docs: DocRow[], docId: string | undefined): UploadedFileDisplay | null {
  if (!docId) return null;
  const d = docs.find((x) => x.id === docId);
  return d ? { name: d.original_filename, sizeBytes: d.byte_size } : null;
}

const FORM_DEFAULTS: Partial<PersonalForm> = {
  citizenship: "KZ",
  gender: "male",
  document_type: "id",
  consent_privacy: false,
  consent_age: false,
};

export default function PersonalPage() {
  const router = useRouter();
  const [applicationId, setApplicationId] = useState<string | null>(null);
  const [identityFileMeta, setIdentityFileMeta] = useState<UploadedFileDisplay | null>(null);
  const [identityUploading, setIdentityUploading] = useState(false);
  const [pageMsg, setPageMsg] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    control,
    reset,
    setValue,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<PersonalForm>({
    resolver: zodResolver(personalFormSchema),
    defaultValues: FORM_DEFAULTS as PersonalForm,
  });

  const uploadIdentityDocument = useCallback(
    async (file: File | null) => {
      if (!file) {
        if (!applicationId) return;
        try {
          const v = getValues();
          let firstName = (v.preferred_first_name ?? "").trim();
          let lastName = (v.preferred_last_name ?? "").trim();

          if (!firstName || !lastName) {
            const app = await apiFetch<{ sections: Record<string, { payload: unknown }> }>("/candidates/me/application");
            const raw = app.sections.personal?.payload as Record<string, unknown> | undefined;
            if (raw) {
              if (!firstName) firstName = String(raw.preferred_first_name ?? "").trim();
              if (!lastName) lastName = String(raw.preferred_last_name ?? "").trim();
            }
          }

          if (!firstName || !lastName) {
            setPageMsg("Невозможно удалить файл: заполните имя и фамилию в разделе «Основная информация».");
            return;
          }

          await apiFetch("/candidates/me/application/sections/personal", {
            method: "PATCH",
            json: {
              payload: {
                ...buildPayload({
                  ...v,
                  preferred_first_name: firstName,
                  preferred_last_name: lastName,
                } as PersonalForm),
                identity_document_id: null,
              },
            },
          });
          setValue("identity_document_id", undefined, { shouldValidate: true, shouldDirty: true });
          setIdentityFileMeta(null);
          bustApiCache("/candidates/me");
          setPageMsg(null);
        } catch (e) {
          setPageMsg(e instanceof Error ? e.message : "Не удалось удалить файл");
        }
        return;
      }

      if (!applicationId) {
        setPageMsg("Не удалось определить заявление. Обновите страницу.");
        return;
      }

      const rollback = identityFileMeta;
      setIdentityFileMeta({ name: file.name, sizeBytes: file.size });
      setIdentityUploading(true);
      setPageMsg(null);

      const fd = new FormData();
      fd.append("application_id", applicationId);
      fd.append("document_type", "supporting_documents");
      fd.append("file", file);
      try {
        const data = await uploadDocumentForm<{
          id: string;
          original_filename?: string;
          byte_size?: number;
        }>(fd);
        setValue("identity_document_id", data.id, { shouldValidate: true, shouldDirty: true });
        setIdentityFileMeta({
          name: data.original_filename ?? file.name,
          sizeBytes: data.byte_size ?? file.size,
        });
        bustApiCache("/candidates/me");
        setPageMsg(null);
      } catch (e) {
        setIdentityFileMeta(rollback);
        setPageMsg(e instanceof ApiError ? e.message : e instanceof Error ? e.message : "Не удалось загрузить файл");
      } finally {
        setIdentityUploading(false);
      }
    },
    [applicationId, getValues, identityFileMeta, setValue],
  );

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{
          application: { id: string };
          sections: Record<string, { payload: unknown }>;
          documents?: DocRow[];
        }>("/candidates/me/application", 2 * 60 * 1000);
        setApplicationId(app.application.id);
        const raw = app.sections.personal?.payload as Record<string, unknown> | undefined;
        const docs = app.documents ?? [];
        const apiValues: Partial<PersonalForm> = raw
          ? {
              preferred_first_name: String(raw.preferred_first_name ?? ""),
              preferred_last_name: String(raw.preferred_last_name ?? ""),
              middle_name: raw.middle_name != null ? String(raw.middle_name) : "",
              date_of_birth: raw.date_of_birth ? String(raw.date_of_birth) : "",
              document_type: raw.document_type === "passport" ? "passport" : "id",
              citizenship: String(raw.citizenship ?? raw.nationality ?? "KZ"),
              iin: raw.iin != null ? String(raw.iin) : "",
              document_number: raw.document_number != null ? String(raw.document_number) : "",
              document_issue_date: raw.document_issue_date ? String(raw.document_issue_date) : "",
              document_issued_by: raw.document_issued_by != null ? String(raw.document_issued_by) : "",
              father_last: raw.father_last != null ? String(raw.father_last) : "",
              father_first: raw.father_first != null ? String(raw.father_first) : "",
              father_middle: raw.father_middle != null ? String(raw.father_middle) : "",
              father_phone: raw.father_phone != null ? String(raw.father_phone) : "",
              mother_last: raw.mother_last != null ? String(raw.mother_last) : "",
              mother_first: raw.mother_first != null ? String(raw.mother_first) : "",
              mother_middle: raw.mother_middle != null ? String(raw.mother_middle) : "",
              mother_phone: raw.mother_phone != null ? String(raw.mother_phone) : "",
              guardian_last: raw.guardian_last != null ? String(raw.guardian_last) : "",
              guardian_first: raw.guardian_first != null ? String(raw.guardian_first) : "",
              guardian_middle: raw.guardian_middle != null ? String(raw.guardian_middle) : "",
              guardian_phone: raw.guardian_phone != null ? String(raw.guardian_phone) : "",
              consent_privacy: Boolean(raw.consent_privacy),
              consent_age: Boolean(raw.consent_age),
              pronouns: raw.pronouns ? String(raw.pronouns) : "",
              gender: raw.gender === "female" ? "female" : "male",
              identity_document_id: raw.identity_document_id != null ? String(raw.identity_document_id) : undefined,
            }
          : {};
        const local = loadDraft<PersonalForm>("personal");
        const merged = { ...FORM_DEFAULTS, ...apiValues, ...local } as PersonalForm;
        reset(merged);
        const idDoc = merged.identity_document_id;
        setIdentityFileMeta(docMetaForId(docs, idDoc));
      } catch (e) {
        if (e instanceof ApiError && e.status === 404) return;
        setPageMsg("Не удалось загрузить данные заявления. Обновите страницу.");
      }
    }
    void load();
  }, [reset]);

  useEffect(() => {
    const sub = watch((_, { name }) => {
      if (name === "consent_privacy" || name === "consent_age") {
        saveDraftLocal("personal", getValues());
      }
    });
    return () => sub.unsubscribe();
  }, [watch, getValues]);

  function buildPayload(data: PersonalForm) {
    return {
      preferred_first_name: data.preferred_first_name,
      preferred_last_name: data.preferred_last_name,
      middle_name: data.middle_name || undefined,
      date_of_birth: data.date_of_birth || undefined,
      document_type: data.document_type || undefined,
      citizenship: data.citizenship || undefined,
      iin: data.iin || undefined,
      document_number: data.document_number || undefined,
      document_issue_date: data.document_issue_date || undefined,
      document_issued_by: data.document_issued_by || undefined,
      father_last: data.father_last || undefined,
      father_first: data.father_first || undefined,
      father_middle: data.father_middle || undefined,
      father_phone: data.father_phone || undefined,
      mother_last: data.mother_last || undefined,
      mother_first: data.mother_first || undefined,
      mother_middle: data.mother_middle || undefined,
      mother_phone: data.mother_phone || undefined,
      guardian_last: data.guardian_last || undefined,
      guardian_first: data.guardian_first || undefined,
      guardian_middle: data.guardian_middle || undefined,
      guardian_phone: data.guardian_phone || undefined,
      consent_privacy: data.consent_privacy,
      consent_age: data.consent_age,
      pronouns: data.pronouns || undefined,
      gender: data.gender,
      identity_document_id: isUuid(data.identity_document_id) ? data.identity_document_id : undefined,
    };
  }

  async function saveDraft() {
    setPageMsg(null);
    const values = getValues();
    saveDraftLocal("personal", values);
    try {
      await apiFetch("/candidates/me/application/sections/personal", {
        method: "PATCH",
        json: { payload: buildPayload(values) },
      });
      bustApiCache("/candidates/me");
      setPageMsg("Черновик сохранен.");
    } catch (e) {
      setPageMsg(e instanceof Error ? e.message : "Не удалось сохранить черновик");
    }
  }

  async function onSubmit(data: PersonalForm) {
    setPageMsg(null);
    try {
      await apiFetch("/candidates/me/application/sections/personal", {
        method: "PATCH",
        json: { payload: buildPayload(data) },
      });
      bustApiCache("/candidates/me");
      clearDraft("personal");
      router.push("/application/contact");
    } catch (e) {
      setPageMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate>
      {pageMsg ? (
        <p className="error" role="alert" style={{ margin: "0 0 16px" }}>
          {pageMsg}
        </p>
      ) : null}
      <FormSection title="Основная информация">
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("preferred_last_name")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("preferred_first_name")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("middle_name")} />
        </div>
        <div className={formStyles.row3}>
          <FormField
            label="Дата рождения"
            placeholder="ДД.ММ.ГГГГ"
            type="text"
            fieldType="date"
            {...register("date_of_birth")}
          />
          <div className={`${formStyles.field} ${formStyles.fieldSpan2}`}>
            <span className={formStyles.label}>Пол</span>
            <Controller
              name="gender"
              control={control}
              render={({ field }) => (
                <PillSegmentedControl
                  aria-label="Пол"
                  options={[
                    { value: "male", label: "Мужской" },
                    { value: "female", label: "Женский" },
                  ]}
                  value={field.value ?? "male"}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
        </div>
        {(errors.preferred_first_name || errors.preferred_last_name || errors.date_of_birth) && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.preferred_first_name?.message || errors.preferred_last_name?.message || errors.date_of_birth?.message}
          </p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Документы">
        <div className={formStyles.row3}>
          <SelectField
            label="Гражданство"
            {...register("citizenship")}
            options={[
              { value: "KZ", label: "Казахстан" },
              { value: "OTHER", label: "Другое" },
            ]}
          />
          <FormField label="ИИН" placeholder="Введите ИИН" fieldType="iin" {...register("iin")} />
        </div>
        <div className={formStyles.row3}>
          <div className={formStyles.field}>
            <span className={formStyles.label}>Тип документа</span>
            <Controller
              name="document_type"
              control={control}
              render={({ field }) => (
                <PillSegmentedControl
                  aria-label="Тип документа"
                  options={[
                    { value: "id", label: "Уд. личности" },
                    { value: "passport", label: "Паспорт" },
                  ]}
                  value={field.value ?? "id"}
                  onChange={field.onChange}
                />
              )}
            />
          </div>
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер документа" placeholder="Введите номер документа" {...register("document_number")} />
          <FormField label="Дата выдачи" placeholder="ДД.ММ.ГГГГ" fieldType="date" {...register("document_issue_date")} />
          <FormField label="Выдан" placeholder="Введите кем выдан" {...register("document_issued_by")} />
        </div>
        <input type="hidden" {...register("identity_document_id")} />
        {(errors.citizenship || errors.iin || errors.document_number || errors.document_issue_date || errors.document_issued_by) && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.citizenship?.message || errors.iin?.message || errors.document_number?.message || errors.document_issue_date?.message || errors.document_issued_by?.message}
          </p>
        )}
        <FileUploadField
          label="Ваш документ"
          hint="Разрешенные форматы: .PDF .JPEG .PNG .HEIC до 10MB"
          uploadedFile={identityFileMeta}
          isUploading={identityUploading}
          onFile={(f) => void uploadIdentityDocument(f)}
        />
        {errors.identity_document_id && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.identity_document_id.message}
          </p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Родители">
        <h3 className={`${formStyles.subheading} ${formStyles.subheadingFirst}`}>Отец</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("father_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("father_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("father_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер телефона" placeholder="+7 777 123 45 67" type="tel" fieldType="phone" {...register("father_phone")} />
        </div>
        {(errors.father_last || errors.father_first || errors.father_phone) && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.father_last?.message || errors.father_first?.message || errors.father_phone?.message}
          </p>
        )}

        <h3 className={formStyles.subheading}>Мать</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("mother_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("mother_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("mother_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField label="Номер телефона" placeholder="+7 777 123 45 67" type="tel" fieldType="phone" {...register("mother_phone")} />
        </div>
        {(errors.mother_last || errors.mother_first || errors.mother_phone) && (
          <p className="error" style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>
            {errors.mother_last?.message || errors.mother_first?.message || errors.mother_phone?.message}
          </p>
        )}

        <h3 className={formStyles.subheading}>Опекун</h3>
        <div className={formStyles.row3}>
          <FormField label="Фамилия" placeholder="Введите фамилию" {...register("guardian_last")} />
          <FormField label="Имя" placeholder="Введите имя" {...register("guardian_first")} />
          <FormField label="Отчество" placeholder="Введите отчество" {...register("guardian_middle")} />
        </div>
        <div className={formStyles.row3}>
          <FormField
            label="Номер телефона"
            placeholder="+7 777 123 45 67"
            type="tel"
            fieldType="phone"
            {...register("guardian_phone")}
          />
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
              <Link href="/privacy">Политикой конфиденциальности</Link>
            </ConsentCheckbox>
          )}
        />
        {errors.consent_privacy && (
          <p style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>{errors.consent_privacy.message}</p>
        )}
        <Controller
          name="consent_age"
          control={control}
          render={({ field }) => (
            <ConsentCheckbox checked={field.value} onChange={field.onChange}>
              Если участнику меньше 18 лет, эту анкету должен заполнить его родитель или законный представитель.
              Продолжая, вы подтверждаете, что вы либо (a) участник в возрасте 18 лет или старше, либо (b) родитель или
              законный представитель, заполняющий эту форму от имени несовершеннолетнего
            </ConsentCheckbox>
          )}
        />
        {errors.consent_age && (
          <p style={{ color: "#dc2626", fontSize: 14, margin: 0 }}>{errors.consent_age.message}</p>
        )}
      </div>

      <Divider />

      {pageMsg && !pageMsg.includes("Не удалось загрузить") && (
        <p className={pageMsg.includes("Не удалось") ? "error" : "muted"} role="status">
          {pageMsg}
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
