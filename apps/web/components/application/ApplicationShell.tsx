"use client";

import { useEffect, useState } from "react";
import { apiFetchCached } from "@/lib/api-client";
import { ApplicationHeader } from "./ApplicationHeader";
import { ApplicationStickyNav } from "./ApplicationStickyNav";
import { ApplicationSidebar } from "./ApplicationSidebar";
import { ApplicationFooter } from "./ApplicationFooter";
import styles from "./application-shell.module.css";

const ME_TTL_MS = 5 * 60 * 1000;

type Props = {
  children: React.ReactNode;
};

export function ApplicationShell({ children }: Props) {
  const [firstName, setFirstName] = useState<string | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiFetchCached<{ profile?: { first_name?: string } | null }>("/auth/me", ME_TTL_MS);
        if (cancelled) return;
        const part = data.profile?.first_name?.trim();
        if (part) setFirstName(part);
      } catch {
        /* unauthenticated or network */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className={styles.page}>
      <ApplicationHeader candidateName={firstName} />
      <ApplicationStickyNav />
      <div className={styles.layoutRow}>
        <main className={styles.main}>{children}</main>
        <div className={styles.sidebarCol}>
          <ApplicationSidebar />
        </div>
      </div>
      <ApplicationFooter />
    </div>
  );
}
