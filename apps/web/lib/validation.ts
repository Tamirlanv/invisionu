import { z } from "zod";

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

export const loginSchema = z.object({
  email: z.string().email({ message: "Укажите корректный email" }),
  password: z.string().min(1, { message: "Введите пароль" }),
});

export const personalSchema = z.object({
  preferred_first_name: z.string().min(1, { message: "Обязательное поле" }),
  preferred_last_name: z.string().min(1, { message: "Обязательное поле" }),
  date_of_birth: z.string().optional(),
  pronouns: z.string().optional(),
});

export const contactSchema = z.object({
  phone_e164: z.string().min(8, { message: "Укажите телефон в формате E.164" }).max(32),
  address_line1: z.string().min(1, { message: "Обязательное поле" }),
  address_line2: z.string().optional(),
  city: z.string().min(1, { message: "Обязательное поле" }),
  region: z.string().optional(),
  postal_code: z.string().optional(),
  country: z.string().length(2, { message: "Код страны ISO-2 (2 буквы)" }),
});

export const educationSchema = z.object({
  entries: z
    .array(
      z.object({
        institution_name: z.string().min(1, { message: "Укажите учебное заведение" }),
        degree_or_program: z.string().optional(),
        field_of_study: z.string().optional(),
        start_date: z.string().optional(),
        end_date: z.string().optional(),
        is_current: z.boolean(),
      }),
    )
    .min(1, { message: "Добавьте хотя бы одну запись об образовании" }),
});

export const socialSchema = z.object({
  attestation: z.string().min(10, { message: "Не менее 10 символов" }).max(2000, { message: "Не более 2000 символов" }),
});
