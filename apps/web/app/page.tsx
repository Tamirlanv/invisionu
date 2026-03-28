import Link from "next/link";

export default function HomePage() {
  return (
    <div>
      <h1 className="h1">inVision U</h1>
      <p className="muted" style={{ maxWidth: 640 }}>
        Портал для подачи заявления. Войдите, чтобы продолжить заполнение анкеты.
      </p>
      <div style={{ display: "flex", gap: 12, marginTop: 18 }}>
        <Link className="btn" href="/login">
          Войти
        </Link>
        <Link className="btn secondary" href="/register">
          Создать аккаунт
        </Link>
      </div>
    </div>
  );
}
