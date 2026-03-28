"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import { loginSchema } from "@/lib/validation";

type Form = z.infer<typeof loginSchema>;

function LoginForm() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next") || "/dashboard";
  const [err, setErr] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(loginSchema) });

  async function onSubmit(data: Form) {
    setErr(null);
    try {
      await apiFetch("/auth/login", { method: "POST", json: data });
      router.replace(next);
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
    <div style={{ maxWidth: 440 }}>
      <h1 className="h1">Вход</h1>
      <p className="muted">Личный кабинет абитуриента.</p>
      <form className="card grid" style={{ marginTop: 16 }} onSubmit={handleSubmit(onSubmit)}>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <div className="error">{errors.email.message}</div>}
        </div>
        <div>
          <label className="label">Пароль</label>
          <input className="input" type="password" autoComplete="current-password" {...register("password")} />
          {errors.password && <div className="error">{errors.password.message}</div>}
        </div>
        {err && <div className="error">{err}</div>}
        <button className="btn" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Вход…" : "Войти"}
        </button>
        <p className="muted" style={{ margin: 0 }}>
          Нет аккаунта? <Link href="/register">Регистрация</Link>
        </p>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="muted">Загрузка…</p>}>
      <LoginForm />
    </Suspense>
  );
}
