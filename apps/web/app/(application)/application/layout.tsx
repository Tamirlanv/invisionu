import Link from "next/link";

const STEPS = [
  { href: "/application/personal", label: "Личные данные" },
  { href: "/application/contact", label: "Контакты" },
  { href: "/application/education", label: "Образование" },
  { href: "/application/internal-test", label: "Внутренний тест" },
  { href: "/application/social-status", label: "Справка о статусе" },
  { href: "/application/review", label: "Проверка" },
];

export default function ApplicationLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 18,
          flexWrap: "wrap",
        }}
      >
        <div style={{ fontWeight: 700 }}>Заявление</div>
        <nav style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
          {STEPS.map((s) => (
            <Link key={s.href} href={s.href} className="btn secondary" style={{ padding: "6px 10px", fontSize: 13 }}>
              {s.label}
            </Link>
          ))}
        </nav>
      </header>
      {children}
    </div>
  );
}
