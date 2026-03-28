import Link from "next/link";
import { LogoutButton } from "@/components/LogoutButton";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return (
    <div>
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 16,
          marginBottom: 22,
          paddingBottom: 16,
          borderBottom: "1px solid rgba(255,255,255,0.08)",
        }}
      >
        <div style={{ fontWeight: 700 }}>inVision U — абитуриент</div>
        <nav style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap" }}>
          <Link href="/dashboard">Главная</Link>
          <Link href="/application/personal">Заявление</Link>
          <LogoutButton />
        </nav>
      </header>
      {children}
    </div>
  );
}
