"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { apiFetch } from "@/lib/api-client";
import { clearAuthTokens, getAuthScopeFromPathname, getRefreshToken } from "@/lib/auth-session";

type LogoutButtonProps = {
  /** По умолчанию — кнопка `.btn.secondary`; для футера анкеты — текстовая ссылка. */
  className?: string;
};

export function LogoutButton({ className }: LogoutButtonProps) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);

  async function logout() {
    setLoading(true);
    const scope = getAuthScopeFromPathname(typeof window === "undefined" ? null : window.location.pathname);
    const refresh = getRefreshToken(scope);
    try {
      await apiFetch("/auth/logout", {
        method: "POST",
        authScope: scope,
        headers: refresh ? { "X-Refresh-Token": refresh } : undefined,
      });
    } finally {
      clearAuthTokens(scope);
      setLoading(false);
      router.replace("/login");
      router.refresh();
    }
  }

  return (
    <button type="button" className={className ?? "btn secondary"} onClick={() => void logout()} disabled={loading}>
      {loading ? "Выход…" : "Выйти"}
    </button>
  );
}
