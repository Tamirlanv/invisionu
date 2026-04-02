"use client";

import Image from "next/image";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";
import { clearAuthTokens } from "@/lib/auth-session";
import styles from "./CommissionSidebar.module.css";

type Props = {
  isOpen: boolean;
  program: string | null;
  onProgramChange: (value: string | null) => void;
};

type NavItem = {
  key: string;
  label: string;
  icon: string;
  href: string;
  active?: boolean;
};

const PROGRAM_ITEMS: NavItem[] = [
  { key: "main", label: "Главная", icon: "/assets/icons/fluent_home-48-filled.svg", href: "/commission", active: true },
  { key: "docs", label: "Документы", icon: "/assets/icons/material-symbols_folder.svg", href: "/commission" },
  { key: "history", label: "История", icon: "/assets/icons/mingcute_time-fill.svg", href: "/commission" },
];

const COMMON_ITEMS: NavItem[] = [
  { key: "interview", label: "Собеседование", icon: "/assets/icons/mdi_user.svg", href: "/commission" },
  { key: "analytics", label: "Аналитика и выгрузка", icon: "/assets/icons/ic_round-bar-chart.svg", href: "/commission" },
];

export function CommissionSidebar({ isOpen, program, onProgramChange }: Props) {
  const router = useRouter();
  const [programMenuOpen, setProgramMenuOpen] = useState(false);
  const programLabel = useMemo(() => {
    if (!program) return "Все";
    const p = program.toLowerCase();
    if (p.includes("foundation")) return "Foundation";
    if (p.includes("бак")) return "Бакалавриат";
    return program;
  }, [program]);

  return (
    <aside className={`${styles.sidebar} ${isOpen ? styles.expanded : styles.collapsed}`}>
      <div className={styles.inner}>
        <div className={styles.header}>
          <button type="button" className={styles.headerSelectBtn} onClick={() => setProgramMenuOpen((v) => !v)}>
            <span className={styles.headerText}>{programLabel}</span>
            <span className={`${styles.chevronIcon} ${programMenuOpen ? styles.chevronIconOpen : ""}`} aria-hidden>
              <svg width="12" height="12" viewBox="0 0 12 12" fill="none">
                <path d="M2 4L6 8L10 4" stroke="#262626" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </span>
          </button>
          {programMenuOpen ? (
            <div className={styles.headerMenu}>
              <button
                type="button"
                className={styles.headerMenuItem}
                onClick={() => {
                  onProgramChange("Бакалавриат");
                  setProgramMenuOpen(false);
                }}
              >
                Бакалавриат
              </button>
              <button
                type="button"
                className={styles.headerMenuItem}
                onClick={() => {
                  onProgramChange("Foundation");
                  setProgramMenuOpen(false);
                }}
              >
                Foundation
              </button>
              <button
                type="button"
                className={styles.headerMenuItem}
                onClick={() => {
                  onProgramChange(null);
                  setProgramMenuOpen(false);
                }}
              >
                Все
              </button>
            </div>
          ) : null}
        </div>

        <div className={styles.section}>
          <p className={styles.sectionTitle}>Программные</p>
          {PROGRAM_ITEMS.map((item) => (
            <Link key={item.key} href={item.href} className={`${styles.item}${item.active ? ` ${styles.active}` : ""}`}>
              <Image src={item.icon} alt="" width={20} height={20} />
              <span className={styles.itemLabel}>{item.label}</span>
            </Link>
          ))}
        </div>

        <div className={styles.section}>
          <p className={styles.sectionTitle}>Общие</p>
          {COMMON_ITEMS.map((item) => (
            <Link key={item.key} href={item.href} className={styles.item}>
              <Image src={item.icon} alt="" width={20} height={20} />
              <span className={styles.itemLabel}>{item.label}</span>
            </Link>
          ))}
        </div>

        <div className={styles.spacer} />

        <button
          type="button"
          className={styles.logoutBtn}
          onClick={() => {
            clearAuthTokens("commission");
            router.push("/login");
          }}
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M7.5 17.5H4.16667C3.72464 17.5 3.30072 17.3244 2.98816 17.0118C2.67559 16.6993 2.5 16.2754 2.5 15.8333V4.16667C2.5 3.72464 2.67559 3.30072 2.98816 2.98816C3.30072 2.67559 3.72464 2.5 4.16667 2.5H7.5" stroke="#e53935" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M13.333 14.1667L17.4997 10L13.333 5.83334" stroke="#e53935" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            <path d="M17.5 10H7.5" stroke="#e53935" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <span className={styles.itemLabel}>Выйти</span>
        </button>
      </div>
    </aside>
  );
}

