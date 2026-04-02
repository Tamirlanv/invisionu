import { z } from "zod";
import { GROWTH_CHAR_LIMITS, GROWTH_QUESTION_IDS } from "./growth-path/constants";
import { normalizeGrowthText } from "./growth-path/text";
import { MAX_MOTIVATION_LETTER_LENGTH, MIN_MOTIVATION_LETTER_LENGTH } from "./motivation-letter";

export const registerSchema = z
  .object({
    email: z.string().email({ message: "Укажите корректный email" }),
    password: z.string().min(12, { message: "Не менее 12 символов" }).max(128, { message: "Не более 128 символов" }),
    first_name: z.string().min(1, { message: "Обязательное поле" }).max(128),
    last_name: z.string().min(1, { message: "Обязательное поле" }).max(128),
  })
  .superRefine((data, ctx) => {
    if (!/[A-Z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна заглавная буква", path: ["password"] });
    }
    if (!/[a-z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна строчная буква", path: ["password"] });
    }
    if (!/\d/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна цифра", path: ["password"] });
    }
  });

/** Форма регистрации (UI): одно поле имени, подтверждение пароля, согласие. */
export const registerPageSchema = z
  .object({
    name: z.string().min(1, { message: "Введите имя" }).max(256),
    email: z.string().email({ message: "Некорректный e-mail" }),
    password: z.string().min(12, { message: "Не менее 12 символов" }).max(128, { message: "Не более 128 символов" }),
    confirmPassword: z.string().min(1, { message: "Подтвердите пароль" }),
    agreedToTerms: z.boolean().refine((v) => v === true, { message: "Необходимо принять соглашение" }),
  })
  .superRefine((data, ctx) => {
    if (!/[A-Z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна заглавная буква", path: ["password"] });
    }
    if (!/[a-z]/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна строчная буква", path: ["password"] });
    }
    if (!/\d/.test(data.password)) {
      ctx.addIssue({ code: "custom", message: "В пароле нужна цифра", path: ["password"] });
    }
    if (data.password !== data.confirmPassword) {
      ctx.addIssue({ code: "custom", message: "Пароли не совпадают", path: ["confirmPassword"] });
    }
  });

export type RegisterPageForm = z.infer<typeof registerPageSchema>;

export const verifyCodeSchema = z.object({
  code: z
    .string()
    .length(6, { message: "Введите 6 цифр" })
    .regex(/^\d{6}$/, { message: "Только цифры" }),
});

export type VerifyCodeForm = z.infer<typeof verifyCodeSchema>;

/** Разбор «Имя Фамилия» в поля API (одно слово → фамилия-заглушка). */
export function splitNameToProfile(name: string): { first_name: string; last_name: string } {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return { first_name: "", last_name: "—" };
  }
  if (parts.length === 1) {
    return { first_name: parts[0], last_name: "—" };
  }
  return { first_name: parts[0], last_name: parts.slice(1).join(" ") };
}

export const loginSchema = z.object({
  email: z.string().email({ message: "Укажите корректный email" }),
  password: z.string().min(1, { message: "Введите пароль" }),
  remember_me: z.boolean().default(false),
});

export const personalSchema = z.object({
  preferred_first_name: z.string().min(1, { message: "Обязательное поле" }),
  preferred_last_name: z.string().min(1, { message: "Обязательное поле" }),
  date_of_birth: z.string().optional(),
  pronouns: z.string().optional(),
});

export const contactSchema = z
  .object({
    phone_e164: z.string().max(32).optional().or(z.literal("")),
    country: z.string().length(2, { message: "Код страны ISO-2 (2 буквы)" }),
    region: z.string().min(1, { message: "Укажите регион" }),
    city: z.string().min(1, { message: "Обязательное поле" }),
    street: z.string().min(1, { message: "Укажите улицу" }),
    house: z.string().min(1, { message: "Укажите дом" }),
    apartment: z.string().min(1, { message: "Укажите квартиру" }),
    address_line2: z.string().optional(),
    postal_code: z.string().optional(),
    instagram: z.string().optional().or(z.literal("")),
    telegram: z.string().optional().or(z.literal("")),
    whatsapp: z.string().optional().or(z.literal("")),
    consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
    consent_parent: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
  })
  .superRefine((data, ctx) => {
    const filled = [data.phone_e164, data.instagram, data.telegram, data.whatsapp].filter(
      (v) => v && v.trim().length > 1 && v.trim() !== "+" && v.trim() !== "@" && v.trim() !== "+7",
    );
    if (filled.length < 2) {
      ctx.addIssue({
        code: "custom",
        message: "Заполните как минимум 2 контактных поля (телефон, Instagram, Telegram или WhatsApp)",
        path: ["phone_e164"],
      });
    }
  });

const educationEntrySchema = z.object({
  institution_name: z.string().min(1, { message: "Укажите учебное заведение" }),
  degree_or_program: z.string().optional(),
  field_of_study: z.string().optional(),
  start_date: z.string().optional(),
  end_date: z.string().optional(),
  is_current: z.boolean(),
});

/** Раздел «Образование»: презентация, язык, сертификаты; entries сохраняются для старых данных. */
export const educationSchema = z.object({
  entries: z.array(educationEntrySchema).max(20).default([]),
  presentation_video_url: z.string().min(1, { message: "Укажите ссылку на презентацию" }),
  english_proof_kind: z.enum(["ielts_6", "toefl_60_78"]),
  certificate_proof_kind: z.enum(["ent", "nis_12"]),
  english_document_id: z.string().min(1, { message: "Загрузите документ по английскому языку" }),
  certificate_document_id: z.string().min(1, { message: "Загрузите сертификат" }),
  additional_document_id: z.string().optional(),
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_parent: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
});

export const socialSchema = z.object({
  attestation: z.string().min(10, { message: "Не менее 10 символов" }).max(2000, { message: "Не более 2000 символов" }),
});

export const motivationSchema = z.object({
  narrative: z
    .string()
    .min(MIN_MOTIVATION_LETTER_LENGTH, { message: `Минимальный объем — ${MIN_MOTIVATION_LETTER_LENGTH} символов.` })
    .max(MAX_MOTIVATION_LETTER_LENGTH, { message: `Максимальный объем — ${MAX_MOTIVATION_LETTER_LENGTH} символов.` }),
  was_pasted: z.boolean().default(false),
  paste_count: z.number().int().nonnegative().default(0),
  last_pasted_at: z.string().nullable().optional(),
});

const growthMetaSchema = z.object({
  was_pasted: z.boolean().default(false),
  paste_count: z.number().int().nonnegative().default(0),
  last_pasted_at: z.string().nullable().optional(),
  typing_count: z.number().int().nonnegative().default(0),
  typing_duration_ms: z.number().int().nonnegative().default(0),
  was_edited_after_paste: z.boolean().default(false),
  delete_count: z.number().int().nonnegative().default(0),
  revision_count: z.number().int().nonnegative().default(0),
});

const growthAnswerSchema = z.object({
  text: z.string().max(700),
  meta: growthMetaSchema.optional(),
});

export const growthPathAnswersSchema = z
  .object({
    q1: growthAnswerSchema,
    q2: growthAnswerSchema,
    q3: growthAnswerSchema,
    q4: growthAnswerSchema,
    q5: growthAnswerSchema,
  })
  .superRefine((answers, ctx) => {
    for (const id of GROWTH_QUESTION_IDS) {
      const { min, max } = GROWTH_CHAR_LIMITS[id];
      const len = normalizeGrowthText(answers[id].text).length;
      if (len < min || len > max) {
        ctx.addIssue({
          code: "custom",
          message: `Ответ: от ${min} до ${max} символов (сейчас ${len}).`,
          path: [id, "text"],
        });
      }
    }
  });

export const growthPathPageSchema = z.object({
  answers: growthPathAnswersSchema,
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_parent: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
});

const achievementLinkSchema = z.object({
  link_type: z.string().max(32),
  label: z.string().max(64),
  url: z
    .string()
    .max(4096)
    .refine((v) => !v.trim() || /^https?:\/\/.+/i.test(v.trim()), {
      message: "Укажите корректную ссылку (https://…)",
    }),
});

export const achievementsSchema = z.object({
  achievements_text: z
    .string()
    .min(250, { message: "Минимальный объем описания — 250 символов." })
    .max(500, { message: "Максимальный объем — 500 символов." }),
  role: z.string().min(1, { message: "Укажите вашу роль" }).max(50),
  year: z
    .string()
    .min(1, { message: "Укажите год" })
    .refine(
      (v) => {
        if (!v || !v.trim()) return false;
        if (!/^\d{4}$/.test(v.trim())) return false;
        const n = Number(v.trim());
        return n >= 2000 && n <= 2035;
      },
      { message: "Укажите год в диапазоне 2000–2035" },
    ),
  links: z.array(achievementLinkSchema).max(8).default([]),
  consent_privacy: z.boolean().refine((v) => v === true, { message: "Необходимо согласие" }),
  consent_parent: z.boolean().refine((v) => v === true, { message: "Необходимо подтверждение" }),
});
