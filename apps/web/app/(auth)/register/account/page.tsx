"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import { storeAuthTokens } from "@/lib/auth-session";
import {
  registerPageSchema,
  splitNameToProfile,
  verifyCodeSchema,
  type RegisterPageForm,
  type VerifyCodeForm,
} from "@/lib/validation";
import { InputField } from "@/components/auth/InputField";
import { TermsCheckbox } from "@/components/auth/TermsCheckbox";
import { RegisterShell } from "@/components/auth/RegisterShell";
import styles from "@/components/auth/auth-register.module.css";
import { clearRegisterFlow, readRegisterFlow } from "@/lib/register-flow";

type Step = "form" | "verify";
type TokenResponse = { access_token: string; refresh_token: string };

export default function RegisterAccountPage() {
  const router = useRouter();
  const [step, setStep] = useState<Step>("form");
  const [pendingEmail, setPendingEmail] = useState<string | null>(null);
  const [apiErr, setApiErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [backHref, setBackHref] = useState("/register");

  const form = useForm<RegisterPageForm>({
    resolver: zodResolver(registerPageSchema),
    defaultValues: {
      name: "",
      email: "",
      password: "",
      confirmPassword: "",
      agreedToTerms: false,
    },
  });

  const verifyForm = useForm<VerifyCodeForm>({
    resolver: zodResolver(verifyCodeSchema),
    defaultValues: { code: "" },
  });

  const agreed = form.watch("agreedToTerms");

  useEffect(() => {
    const flow = readRegisterFlow();
    if (!flow?.program) {
      router.replace("/register");
      return;
    }
    if (flow.program === "bachelor" && !flow.specialtyId) {
      router.replace("/register/specialty");
      return;
    }
    setBackHref(flow.program === "bachelor" ? "/register/specialty" : "/register");
    setReady(true);
  }, [router]);

  async function onSubmitForm(data: RegisterPageForm) {
    setApiErr(null);
    const { first_name, last_name } = splitNameToProfile(data.name);
    try {
      await apiFetch("/auth/register", {
        method: "POST",
        json: {
          email: data.email,
          password: data.password,
          first_name,
          last_name,
        },
      });
      setPendingEmail(data.email.trim().toLowerCase());
      setStep("verify");
      verifyForm.reset({ code: "" });
    } catch (e) {
      if (e instanceof ApiError) {
        setApiErr(e.message);
      } else {
        setApiErr("Не удалось зарегистрироваться");
      }
    }
  }

  async function onSubmitVerify(data: VerifyCodeForm) {
    if (!pendingEmail) {
      setApiErr("Сначала заполните регистрацию.");
      return;
    }
    setApiErr(null);
    try {
      const auth = await apiFetch<TokenResponse>("/auth/register/complete", {
        method: "POST",
        json: { email: pendingEmail, code: data.code },
      });
      storeAuthTokens("candidate", { accessToken: auth.access_token, refreshToken: auth.refresh_token });
      clearRegisterFlow();
      router.replace("/application/personal?welcome=1");
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setApiErr(e.message);
      } else {
        setApiErr("Не удалось подтвердить код");
      }
    }
  }

  function goBackToForm() {
    setStep("form");
    setPendingEmail(null);
    setApiErr(null);
  }

  if (!ready) {
    return (
      <RegisterShell backHref="/register">
        <p className={styles.verifyHint}>Загрузка…</p>
      </RegisterShell>
    );
  }

  return (
    <RegisterShell
      backHref={backHref}
      onBack={step === "verify" ? goBackToForm : undefined}
    >
      {step === "form" ? (
        <form className={styles.formColumn} onSubmit={form.handleSubmit(onSubmitForm)} noValidate>
          <h1 className={styles.title}>Регистрация</h1>

          <div className={styles.fields}>
            <div className={styles.fieldStack}>
              <Controller
                name="name"
                control={form.control}
                render={({ field }) => (
                  <InputField
                    label="Имя"
                    placeholder="Введите имя"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={form.formState.errors.name?.message}
                    autoComplete="name"
                  />
                )}
              />
              <Controller
                name="email"
                control={form.control}
                render={({ field }) => (
                  <InputField
                    label="E-mail"
                    type="email"
                    placeholder="Введите e-mail"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={form.formState.errors.email?.message}
                    autoComplete="email"
                  />
                )}
              />
              <Controller
                name="password"
                control={form.control}
                render={({ field }) => (
                  <InputField
                    label="Пароль"
                    type="password"
                    placeholder="Введите пароль"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={form.formState.errors.password?.message}
                    autoComplete="new-password"
                  />
                )}
              />
              <Controller
                name="confirmPassword"
                control={form.control}
                render={({ field }) => (
                  <InputField
                    label="Подтвердить пароль"
                    type="password"
                    placeholder="Введите пароль"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={form.formState.errors.confirmPassword?.message}
                    autoComplete="new-password"
                  />
                )}
              />
            </div>

            <TermsCheckbox
              checked={agreed}
              onChange={(v) => form.setValue("agreedToTerms", v, { shouldValidate: true })}
              error={form.formState.errors.agreedToTerms?.message}
            />
          </div>

          <div className={styles.actions}>
            {apiErr ? <p className={styles.apiError}>{apiErr}</p> : null}
            <button type="submit" className="btn" disabled={form.formState.isSubmitting}>
              {form.formState.isSubmitting ? "Отправка…" : "Продолжить"}
            </button>
            <p className={styles.footerLine}>
              <span>Уже есть аккаунт? </span>
              <Link href="/login" className={styles.footerLink}>
                Войти
              </Link>
            </p>
          </div>
        </form>
      ) : (
        <form className={styles.formColumn} onSubmit={verifyForm.handleSubmit(onSubmitVerify)} noValidate>
          <h1 className={styles.title}>Верификация</h1>
          {pendingEmail ? (
            <p className={styles.verifyHint}>Код отправлен на {pendingEmail}</p>
          ) : null}

          <div className={styles.fields}>
            <div className={styles.fieldStack}>
              <Controller
                name="code"
                control={verifyForm.control}
                render={({ field }) => (
                  <InputField
                    label="Код"
                    placeholder="Введите код из почты"
                    name={field.name}
                    value={field.value}
                    onChange={(v) => field.onChange(v.replace(/\D/g, "").slice(0, 6))}
                    onBlur={field.onBlur}
                    error={verifyForm.formState.errors.code?.message}
                    autoComplete="one-time-code"
                    inputMode="numeric"
                  />
                )}
              />
            </div>
          </div>

          <div className={styles.actions}>
            {apiErr ? <p className={styles.apiError}>{apiErr}</p> : null}
            <button type="submit" className="btn" disabled={verifyForm.formState.isSubmitting}>
              {verifyForm.formState.isSubmitting ? "Проверка…" : "Продолжить"}
            </button>
            <button type="button" className={styles.backLink} onClick={goBackToForm}>
              Назад к регистрации
            </button>
          </div>
        </form>
      )}
    </RegisterShell>
  );
}
