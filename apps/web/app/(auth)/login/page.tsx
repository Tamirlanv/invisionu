"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import { loginSchema } from "@/lib/validation";
import { InputField } from "@/components/auth/InputField";
import styles from "@/components/auth/auth-register.module.css";

const LOGO_SRC = "/assets/images/Gemini_Generated_Image_7vjh7a7vjh7a7vjh.png";

type Form = z.infer<typeof loginSchema>;

function LoginFormInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");
  const [err, setErr] = useState<string | null>(null);
  const {
    control,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "", remember_me: false },
  });

  async function onSubmit(data: Form) {
    setErr(null);
    try {
      await apiFetch("/auth/login", { method: "POST", json: data });

      // If "next" was explicitly requested by middleware, honor it.
      if (next) {
        router.replace(next);
        router.refresh();
        return;
      }

      // Role-aware default landing:
      // - commission users -> /commission
      // - candidate users -> /application/personal
      try {
        await apiFetch("/commission/me");
        router.replace("/commission");
      } catch {
        router.replace("/application/personal");
      }
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
      } else {
        setErr("Не удалось войти");
      }
    }
  }

  return (
    <div className={styles.root}>
      <div className={styles.panelLeft}>
        <div className={styles.logoWrap}>
          <Image
            src={LOGO_SRC}
            alt="inVision"
            fill
            sizes="(max-width: 900px) 80vw, 474px"
            priority
            style={{ objectFit: "contain" }}
          />
        </div>
      </div>

      <div className={styles.panelRight}>
        <form className={styles.formColumn} onSubmit={handleSubmit(onSubmit)} noValidate>
          <h1 className={styles.title}>Вход</h1>
          <p className={styles.verifyHint} style={{ marginTop: 0 }}>
            Личный кабинет абитуриента
          </p>

          <div className={styles.fields}>
            <div className={styles.fieldStack}>
              <Controller
                name="email"
                control={control}
                render={({ field }) => (
                  <InputField
                    label="E-mail"
                    type="email"
                    placeholder="Введите e-mail"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={errors.email?.message}
                    autoComplete="email"
                  />
                )}
              />
              <Controller
                name="password"
                control={control}
                render={({ field }) => (
                  <InputField
                    label="Пароль"
                    type="password"
                    placeholder="Введите пароль"
                    name={field.name}
                    value={field.value}
                    onChange={field.onChange}
                    onBlur={field.onBlur}
                    error={errors.password?.message}
                    autoComplete="current-password"
                  />
                )}
              />
              <Controller
                name="remember_me"
                control={control}
                render={({ field }) => (
                  <div className={styles.checkboxRowCenter}>
                    <button
                      type="button"
                      className={`${styles.checkboxBtn} ${field.value ? styles.checkboxBtnChecked : ""}`}
                      onClick={() => field.onChange(!field.value)}
                      aria-label="Запомнить меня"
                      aria-pressed={field.value}
                    >
                      {field.value ? (
                        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" aria-hidden>
                          <path
                            d="M2 6L5 9L10 3"
                            stroke="white"
                            strokeWidth="2"
                            strokeLinecap="round"
                            strokeLinejoin="round"
                          />
                        </svg>
                      ) : null}
                    </button>
                    <p className={styles.checkboxText}>Запомнить меня</p>
                  </div>
                )}
              />
            </div>
          </div>

          <div className={styles.actions}>
            {err ? <p className={styles.apiError}>{err}</p> : null}
            <button type="submit" className="btn" disabled={isSubmitting}>
              {isSubmitting ? "Вход…" : "Продолжить"}
            </button>
            <p className={styles.footerLine}>
              <span>Нет аккаунта? </span>
              <Link href="/register" className={styles.footerLink}>
                Регистрация
              </Link>
            </p>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="muted" style={{ padding: 48, textAlign: "center" }}>Загрузка…</p>}>
      <LoginFormInner />
    </Suspense>
  );
}
