import Link from "next/link";

export default function CommissionApplicationNotFound() {
  return (
    <main style={{ display: "grid", gap: 12 }}>
      <p className="error">Заявка не найдена.</p>
      <Link href="/commission">← К доске</Link>
    </main>
  );
}

