"use client";

import type { ReactNode } from "react";
import type { CommissionApplicationPersonalInfoView } from "@/lib/commission/types";

type Props = {
  data: CommissionApplicationPersonalInfoView;
  moveButton?: ReactNode;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
};

const FILE_ICON = (
  <svg width="36" height="36" viewBox="0 0 36 36" fill="none" aria-hidden="true">
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M10.5 3C8.01472 3 6 5.01472 6 7.5V28.5C6 30.9853 8.01472 33 10.5 33H25.5C27.9853 33 30 30.9853 30 28.5V14.1213C30 12.8953 29.5129 11.7196 28.6464 10.8536L22.1464 4.35355C21.2804 3.4875 20.1046 3 18.8787 3H10.5ZM12 19.5C12 18.6716 12.6716 18 13.5 18H22.5C23.3284 18 24 18.6716 24 19.5C24 20.3284 23.3284 21 22.5 21H13.5C12.6716 21 12 20.3284 12 19.5ZM13.5 24C12.6716 24 12 24.6716 12 25.5C12 26.3284 12.6716 27 13.5 27H19.5C20.3284 27 21 26.3284 21 25.5C21 24.6716 20.3284 24 19.5 24H13.5Z"
      fill="#262626"
    />
    <path
      d="M21 3.25V9C21 11.2091 22.7909 13 25 13H30.75C30.6155 12.4907 30.3484 12.0175 29.9749 11.6339L22.3661 3.02513C21.9826 2.65164 21.5093 2.38449 21 2.25V3.25Z"
      fill="#262626"
    />
  </svg>
);

/* label/value pair — 14px */
function Field({ label, value }: { label: string; value: string | number | null | undefined }) {
  if (value === null || value === undefined || value === "") return null;
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>
        {label}
      </p>
      <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#262626", letterSpacing: "-0.42px", lineHeight: "14px" }}>
        {String(value)}
      </p>
    </div>
  );
}

/* section heading style */
const sectionTitle: React.CSSProperties = {
  margin: 0,
  fontSize: 20,
  fontWeight: 550,
  color: "#262626",
  letterSpacing: "-0.6px",
  lineHeight: "20px",
};

const STAGE_PILLS = ["Оценка заявки", "Собеседование", "Решение комиссии"] as const;
const TABS = ["Личная информация", "Тест", "Мотивация", "Путь", "Достижения"] as const;

export function PersonalInfoSection({ data, moveButton, activeTab, onTabChange }: Props) {
  const { personalInfo } = data;
  const currentTab = activeTab ?? TABS[0];

  return (
    <div style={{ display: "grid", gap: 24, minWidth: 0 }}>
      {/* ── Stage nav ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={sectionTitle}>Этап</h2>
        </div>
        <div
          style={{
            display: "inline-flex",
            alignItems: "center",
            background: "#f1f1f1",
            borderRadius: 100,
            padding: 2,
            position: "relative",
          }}
        >
          {STAGE_PILLS.map((pill, i) => (
            <span
              key={pill}
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: "10px 16px",
                borderRadius: 100,
                fontSize: 14,
                fontWeight: 350,
                letterSpacing: "-0.42px",
                lineHeight: "14px",
                whiteSpace: "nowrap",
                cursor: "default",
                background: i === 0 ? "#98da00" : "transparent",
                color: i === 0 ? "#fff" : "#626262",
                transition: "background 0.3s ease, color 0.3s ease",
              }}
            >
              {pill}
            </span>
          ))}
        </div>
      </div>

      {/* ── "Оценка заявки" title + tab bar ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
          <h2 style={sectionTitle}>Оценка заявки</h2>
        </div>
        <div style={{ display: "flex", gap: 32, alignItems: "center" }}>
          {TABS.map((tab) => {
            const isActive = tab === currentTab;
            return (
              <span
                key={tab}
                role="button"
                tabIndex={0}
                onClick={() => onTabChange?.(tab)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") onTabChange?.(tab);
                }}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  padding: "10px 0",
                  fontSize: 14,
                  fontWeight: 350,
                  letterSpacing: "-0.42px",
                  lineHeight: "14px",
                  whiteSpace: "nowrap",
                  cursor: "pointer",
                  color: isActive ? "#262626" : "#626262",
                  borderBottom: isActive ? "2px solid #98da00" : "2px solid transparent",
                  transition: "color 0.2s ease, border-bottom-color 0.2s ease",
                }}
              >
                {tab}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── Personal info content (only when this tab is active) ── */}
      {currentTab !== "Личная информация" ? null : (
      <>
      {/* ── Основная информация ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <h3 style={sectionTitle}>Основная информация</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, 1fr)" }}>
          <Field label="ФИО" value={personalInfo.basicInfo.fullName} />
          <Field label="Пол" value={personalInfo.basicInfo.gender} />
          <Field label="Дата рождения" value={personalInfo.basicInfo.birthDate} />
        </div>
      </div>

      {/* ── Родители ── */}
      {personalInfo.guardians.length > 0 ? (
        <div style={{ display: "grid", gap: 12 }}>
          <h3 style={sectionTitle}>Родители</h3>
          {/* Column headers */}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>Роль</p>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>ФИО</p>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>Номер телефона</p>
          </div>
          {/* Rows */}
          {personalInfo.guardians.map((g) => (
            <div
              key={`${g.role}-${g.fullName}`}
              style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}
            >
              <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#262626", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                {g.role}
              </p>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#262626", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                {g.fullName}
              </p>
              <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#262626", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                {g.phone ?? "—"}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      {/* ── Домашний адрес ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <h3 style={sectionTitle}>Домашний адрес</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, 1fr)" }}>
          <Field label="Страна" value={personalInfo.address.country} />
          <Field label="Регион" value={personalInfo.address.region} />
          <Field label="Город" value={personalInfo.address.city} />
        </div>
        <Field label="Полный адрес" value={personalInfo.address.fullAddress} />
      </div>

      {/* ── Контактные данные ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <h3 style={sectionTitle}>Контактные данные</h3>
        <div style={{ display: "grid", gap: 12, gridTemplateColumns: "repeat(3, 1fr)" }}>
          <Field label="Телефон" value={personalInfo.contacts.phone} />
          <Field label="Instagram" value={personalInfo.contacts.instagram} />
          <Field label="Telegram" value={personalInfo.contacts.telegram} />
          <Field label="WhatsApp" value={personalInfo.contacts.whatsapp} />
        </div>
      </div>

      {/* ── Документы ── */}
      <div style={{ display: "grid", gap: 12 }}>
        <h3 style={sectionTitle}>Документы</h3>
        {personalInfo.documents.length === 0 ? (
          <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262" }}>Документы не прикреплены.</p>
        ) : (
          <div style={{ display: "grid", gap: 10, gridTemplateColumns: "repeat(3, 1fr)" }}>
            {personalInfo.documents.map((doc) => (
              <div key={doc.id} style={{ display: "grid", gap: 8 }}>
                <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                  {doc.type}
                </p>
                <div
                  style={{
                    border: "1px solid #e1e1e1",
                    borderRadius: 8,
                    padding: 24,
                    display: "flex",
                    gap: 10,
                    alignItems: "center",
                  }}
                >
                  {FILE_ICON}
                  <div style={{ display: "grid", gap: 4 }}>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 450, color: "#262626", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                      {doc.fileName}
                    </p>
                    {doc.fileSize ? (
                      <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                        {doc.fileSize}
                      </p>
                    ) : null}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Video presentation */}
        {personalInfo.videoPresentation?.url ? (
          <div style={{ display: "grid", gap: 4 }}>
            <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px" }}>
              Видео-презентация
            </p>
            <a
              href={personalInfo.videoPresentation.url}
              target="_blank"
              rel="noreferrer"
              style={{ fontSize: 14, fontWeight: 350, color: "#4facea", letterSpacing: "-0.42px", textDecoration: "none" }}
            >
              {personalInfo.videoPresentation.url}
            </a>
          </div>
        ) : null}
      </div>

      {/* ── Далее / move action ── */}
      {moveButton ?? null}
      </>
      )}
    </div>
  );
}
