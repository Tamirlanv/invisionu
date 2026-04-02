"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useForm, Controller } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { contactSchema } from "@/lib/validation";
import { FormSection } from "@/components/application/FormSection";
import { FormField } from "@/components/application/FormField";
import { SelectField } from "@/components/application/SelectField";
import { Divider } from "@/components/application/Divider";
import { ConsentCheckbox } from "@/components/application/ConsentCheckbox";
import { saveDraft as saveDraftLocal, loadDraft, clearDraft } from "@/lib/draft-storage";
import formStyles from "@/components/application/form-ui.module.css";
import { z } from "zod";

type Form = z.infer<typeof contactSchema>;

function buildAddressLine1(street: string, house?: string | null, apartment?: string | null) {
  const h = house?.trim();
  const a = apartment?.trim();
  const parts = [street.trim(), h ? `д. ${h}` : "", a ? `кв. ${a}` : ""].filter(Boolean);
  return parts.join(", ");
}

const DEFAULTS: Partial<Form> = {
  country: "KZ",
  consent_privacy: false,
  consent_parent: false,
  phone_e164: "+7",
  whatsapp: "+7",
  instagram: "@",
  telegram: "@",
};

export default function ContactPage() {
  const router = useRouter();
  const [msg, setMsg] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    reset,
    control,
    getValues,
    watch,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(contactSchema),
    defaultValues: DEFAULTS as Form,
  });

  useEffect(() => {
    async function load() {
      try {
        const app = await apiFetchCached<{ sections: Record<string, { payload: unknown }> }>(
          "/candidates/me/application",
          2 * 60 * 1000,
        );
        const raw = app.sections.contact?.payload as Record<string, unknown> | undefined;
        const apiValues: Partial<Form> = raw
          ? {
              phone_e164: String(raw.phone_e164 ?? DEFAULTS.phone_e164),
              country: String(raw.country ?? "KZ"),
              region: raw.region != null ? String(raw.region) : "",
              city: String(raw.city ?? ""),
              street:
                raw.street != null
                  ? String(raw.street)
                  : raw.address_line1 != null
                    ? String(raw.address_line1)
                    : "",
              house: raw.house != null ? String(raw.house) : "",
              apartment: raw.apartment != null ? String(raw.apartment) : "",
              address_line2: raw.address_line2 != null ? String(raw.address_line2) : "",
              postal_code: raw.postal_code != null ? String(raw.postal_code) : "",
              instagram: raw.instagram != null ? String(raw.instagram) : DEFAULTS.instagram,
              telegram: raw.telegram != null ? String(raw.telegram) : DEFAULTS.telegram,
              whatsapp: raw.whatsapp != null ? String(raw.whatsapp) : DEFAULTS.whatsapp,
              consent_privacy: Boolean(raw.consent_privacy),
              consent_parent: Boolean(raw.consent_parent),
            }
          : {};
        const local = loadDraft<Form>("contact");
        reset({ ...DEFAULTS, ...apiValues, ...local } as Form);
      } catch {
        /* ignore */
      }
    }
    void load();
  }, [reset]);

  useEffect(() => {
    const sub = watch((_, { name }) => {
      if (name === "consent_privacy" || name === "consent_parent") {
        saveDraftLocal("contact", getValues());
      }
    });
    return () => sub.unsubscribe();
  }, [watch, getValues]);

  function buildPayload(data: Form) {
    const address_line1 = buildAddressLine1(data.street, data.house, data.apartment);
    return {
      phone_e164: data.phone_e164,
      country: data.country,
      region: data.region || undefined,
      city: data.city,
      address_line1,
      address_line2: data.address_line2 || undefined,
      postal_code: data.postal_code || undefined,
      street: data.street,
      house: data.house || undefined,
      apartment: data.apartment || undefined,
      instagram: data.instagram || undefined,
      telegram: data.telegram || undefined,
      whatsapp: data.whatsapp || undefined,
      consent_privacy: data.consent_privacy,
      consent_parent: data.consent_parent,
    };
  }

  async function saveDraft() {
    setMsg(null);
    const values = getValues();
    saveDraftLocal("contact", values);
    try {
      await apiFetch("/candidates/me/application/sections/contact", {
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
      await apiFetch("/candidates/me/application/sections/contact", {
        method: "PATCH",
        json: { payload: buildPayload(data) },
      });
      bustApiCache("/candidates/me");
      clearDraft("contact");
      router.push("/application/education");
    } catch (e) {
      setMsg(e instanceof Error ? e.message : "Не удалось сохранить");
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)} noValidate style={{ maxWidth: 872 }}>
      <h1 className="h1" style={{ fontSize: 20, marginBottom: 24 }}>
        Контакты
      </h1>

      <FormSection title="Домашний адрес">
        <div className={formStyles.row3}>
          <SelectField
            label="Страна"
            {...register("country")}
            options={[
              { value: "KZ", label: "Казахстан" },
              { value: "KG", label: "Кыргызстан" },
              { value: "UZ", label: "Узбекистан" },
              { value: "RU", label: "Россия" },
            ]}
          />
          <FormField label="Регион" placeholder="Введите регион" {...register("region")} />
          <FormField label="Город" placeholder="Введите город" {...register("city")} />
        </div>

        <div className={formStyles.row3}>
          <FormField label="Улица" placeholder="Введите улицу" {...register("street")} />
          <FormField label="Дом" placeholder="Введите номер дома" {...register("house")} />
          <FormField label="Квартира" placeholder="Введите номер квартиры" {...register("apartment")} />
        </div>

        {(errors.region || errors.city || errors.street || errors.house || errors.apartment) && (
          <p className="error">
            {errors.region?.message || errors.city?.message || errors.street?.message || errors.house?.message || errors.apartment?.message}
          </p>
        )}
      </FormSection>

      <Divider />

      <FormSection title="Контактные данные">
        <div className={formStyles.row3}>
          <FormField label="Телефон" placeholder="+7 777 123 45 67" fieldType="phone" {...register("phone_e164")} />
          <FormField label="Instagram" placeholder="@username" fieldType="latin_username" {...register("instagram")} />
          <FormField label="Telegram" placeholder="@username" fieldType="latin_username" {...register("telegram")} />
        </div>

        <div className={formStyles.row3}>
          <FormField label="WhatsApp" placeholder="+7 777 123 45 67" fieldType="phone" {...register("whatsapp")} />
        </div>

        {errors.phone_e164 && <p className="error">{errors.phone_e164.message}</p>}
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
  );
}
