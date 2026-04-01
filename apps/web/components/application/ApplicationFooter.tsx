"use client";

import Link from "next/link";
import { LogoutButton } from "@/components/LogoutButton";
import styles from "./application-footer.module.css";

export function ApplicationFooter() {
  return (
    <footer className={styles.footer}>
      <div className={styles.inner}>
        <nav className={styles.nav} aria-label="Нижняя навигация">
          <Link href="/application/personal" className={styles.link}>
            Настройки
          </Link>
          <LogoutButton className={styles.linkButton} />
        </nav>
        <p className={styles.copy}>© {new Date().getFullYear()} inVision U. Все права защищены.</p>
      </div>
    </footer>
  );
}
