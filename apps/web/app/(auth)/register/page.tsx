"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { apiFetch, ApiError } from "@/lib/api-client";
import { registerSchema } from "@/lib/validation";

type Form = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const router = useRouter();
  const [err, setErr] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<Form>({ resolver: zodResolver(registerSchema) });

  async function onSubmit(data: Form) {
    setErr(null);
    try {
      await apiFetch("/auth/register", { method: "POST", json: data });
      router.replace("/dashboard?welcome=1");
      router.refresh();
    } catch (e) {
      if (e instanceof ApiError) {
        setErr(e.message);
      } else {
        setErr("Не удалось зарегистрироваться");
      }
    }
  }

  return (
    <div style={{ maxWidth: 480 }}>
      <h1 className="h1">Регистрация</h1>
      <p className="muted">Создайте аккаунт абитуриента inVision U.</p>
      <form className="card grid" style={{ marginTop: 16 }} onSubmit={handleSubmit(onSubmit)}>
        <div>
          <label className="label">Email</label>
          <input className="input" type="email" autoComplete="email" {...register("email")} />
          {errors.email && <div className="error">{errors.email.message}</div>}
        </div>
        <div>
          <label className="label">Пароль</label>
          <input className="input" type="password" autoComplete="new-password" {...register("password")} />
          {errors.password && <div className="error">{errors.password.message}</div>}
        </div>
        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
          <div>
            <label className="label">Имя</label>
            <input className="input" {...register("first_name")} />
            {errors.first_name && <div className="error">{errors.first_name.message}</div>}
          </div>
          <div>
            <label className="label">Фамилия</label>
            <input className="input" {...register("last_name")} />
            {errors.last_name && <div className="error">{errors.last_name.message}</div>}
          </div>
        </div>
        {err && <div className="error">{err}</div>}
        <button className="btn" type="submit" disabled={isSubmitting}>
          {isSubmitting ? "Создание…" : "Создать аккаунт"}
        </button>
        <p className="muted" style={{ margin: 0 }}>
          Уже есть аккаунт? <Link href="/login">Войти</Link>
        </p>
      </form>
    </div>
  );
}
