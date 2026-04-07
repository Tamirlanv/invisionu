"use client";

import type { ReactNode } from "react";
import Image from "next/image";
import { useState } from "react";
import type { CommissionApplicationPersonalInfoView } from "@/lib/commission/types";
import formUiStyles from "@/components/application/form-ui.module.css";
import { PillSegmentedControl } from "@/components/application/PillSegmentedControl";
import { CommissionCandidateAiInterviewPanel } from "@/components/commission/detail/CommissionCandidateAiInterviewPanel";
import { CommissionInterviewWithCommissionPanel } from "@/components/commission/detail/CommissionInterviewWithCommissionPanel";
import docCardStyles from "@/components/commission/detail/personal-info-document-card.module.css";
import tabTransitionStyles from "@/components/commission/detail/commission-tab-transitions.module.css";
import { openCommissionApplicationDocumentInNewTab } from "@/lib/commission/query";

type Props = {
  data: CommissionApplicationPersonalInfoView;
  readOnly?: boolean;
  moveButton?: ReactNode;
  canOpenVideoReview?: boolean;
  onOpenVideoReview?: () => void;
  activeTab?: string;
  onTabChange?: (tab: string) => void;
  /** 0 = первый столбец воронки (Проверка данных или Оценка заявки), 1 = Собеседование, 2 = Решение комиссии. */
  commissionPillIndex: number;
  onCommissionPillChange: (index: number) => void;
  interviewSubTab: string;
  onInterviewSubTabChange: (tab: string) => void;
  interviewPrepSlot: ReactNode;
  /** True while кандидат на этапе «Проверка данных» (API: `data_check` или legacy `initial_screening`). */
  isDataVerificationStage: boolean;
};

function CommissionDocumentOpenButton({
  applicationId,
  doc,
}: {
  applicationId: string;
  doc: { id: string; fileName: string; fileSize: string | null };
}) {
  const [busy, setBusy] = useState(false);
  async function onOpen() {
    if (busy) return;
    setBusy(true);
    try {
      await openCommissionApplicationDocumentInNewTab(applicationId, doc.id);
    } catch (e) {
      window.alert(e instanceof Error ? e.message : "Не удалось открыть файл");
    } finally {
      setBusy(false);
    }
  }
  return (
    <button
      type="button"
      className={docCardStyles.card}
      disabled={busy}
      onClick={() => void onOpen()}
      aria-label={`Открыть документ ${doc.fileName}`}
    >
      <Image
        className={docCardStyles.icon}
        src="/assets/icons/solar_file-bold.svg"
        alt=""
        width={36}
        height={36}
        unoptimized
      />
      <div className={docCardStyles.body}>
        <div className={docCardStyles.info}>
          <p className={formUiStyles.uploadFileCardName} title={doc.fileName}>
            {doc.fileName}
          </p>
          {doc.fileSize ? <p className={formUiStyles.uploadFileCardSize}>{doc.fileSize}</p> : null}
        </div>
        <span className={docCardStyles.viewLabel}>Смотреть</span>
      </div>
    </button>
  );
}

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

function commissionStageOptions(isDataVerificationStage: boolean) {
  return [
    { value: "0", label: isDataVerificationStage ? "Проверка данных" : "Оценка заявки" },
    { value: "1", label: "Собеседование" },
    { value: "2", label: "Решение комиссии" },
  ] as const;
}
const TABS = ["Личная информация", "Тест", "Мотивация", "Путь", "Достижения"] as const;
const INTERVIEW_SUB_TABS = ["Подготовка вопросов", "AI-собеседование", "Собеседование с комиссией"] as const;

export function PersonalInfoSection({
  data,
  readOnly = false,
  moveButton,
  canOpenVideoReview = false,
  onOpenVideoReview,
  activeTab,
  onTabChange,
  commissionPillIndex,
  onCommissionPillChange,
  interviewSubTab,
  onInterviewSubTabChange,
  interviewPrepSlot,
  isDataVerificationStage,
}: Props) {
  const { personalInfo } = data;
  const currentTab = activeTab ?? TABS[0];
  const firstColumnTitle = isDataVerificationStage ? "Проверка данных" : "Оценка заявки";

  return (
    <div style={{ display: "grid", gap: 24, minWidth: 0 }}>
      {/* ── Stage nav: скрыт на этапе «Проверка данных» (нет переключения колонок доски) ── */}
      {!isDataVerificationStage ? (
        <div style={{ display: "grid", gap: 12 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <h2 style={sectionTitle}>Этап</h2>
          </div>
          <PillSegmentedControl
            aria-label="Этап"
            options={[...commissionStageOptions(isDataVerificationStage)]}
            value={String(commissionPillIndex) as "0" | "1" | "2"}
            onChange={(v) => onCommissionPillChange(Number(v))}
          />
        </div>
      ) : null}

      {commissionPillIndex === 0 ? (
        <>
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={sectionTitle}>{firstColumnTitle}</h2>
            </div>
            <div style={{ display: "flex", gap: 32, alignItems: "center", flexWrap: "wrap" }}>
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

          {currentTab !== "Личная информация" ? null : (
            <div key="personal" className={tabTransitionStyles.tabPanelEnter}>
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
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>Роль</p>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>ФИО</p>
                    <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>Номер телефона</p>
                  </div>
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
                  <div
                    style={{
                      display: "grid",
                      gap: 10,
                      gridTemplateColumns: "repeat(3, minmax(0, 1fr))",
                    }}
                  >
                    {personalInfo.documents.map((doc) => (
                      <div key={doc.id} style={{ display: "grid", gap: 8, minWidth: 0 }}>
                        <p style={{ margin: 0, fontSize: 14, fontWeight: 350, color: "#626262", letterSpacing: "-0.42px", lineHeight: "14px" }}>
                          {doc.type}
                        </p>
                        <CommissionDocumentOpenButton applicationId={data.applicationId} doc={doc} />
                      </div>
                    ))}
                  </div>
                )}

                {personalInfo.videoPresentation?.url ? (
                  <div style={{ display: "grid", gap: 8 }}>
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
                    {canOpenVideoReview ? (
                      <button
                        type="button"
                        className="btn"
                        onClick={onOpenVideoReview}
                        style={{ width: "100%", boxSizing: "border-box" }}
                      >
                        Проверить видео
                      </button>
                    ) : null}
                  </div>
                ) : null}
              </div>

              {moveButton ?? null}
            </div>
          )}
        </>
      ) : null}

      {!isDataVerificationStage && commissionPillIndex === 1 ? (
        <>
          {/* Как «Оценка заявки»: отдельный блок заголовка + вкладок (gap 12), контент — сосед снаружи (gap 24 у корня). */}
          <div style={{ display: "grid", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <h2 style={sectionTitle}>Собеседования</h2>
            </div>
            <div style={{ display: "flex", gap: 32, alignItems: "center", flexWrap: "wrap" }}>
              {INTERVIEW_SUB_TABS.map((tab) => {
                const isActive = tab === interviewSubTab;
                return (
                  <span
                    key={tab}
                    role="button"
                    tabIndex={0}
                    onClick={() => onInterviewSubTabChange(tab)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") onInterviewSubTabChange(tab);
                    }}
                    style={{
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      padding: "10px 0",
                      minHeight: 34,
                      boxSizing: "border-box",
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

          <div key={interviewSubTab} className={tabTransitionStyles.tabPanelEnter}>
            {interviewSubTab === "Подготовка вопросов" ? interviewPrepSlot : null}
            {interviewSubTab === "AI-собеседование" ? (
              <CommissionCandidateAiInterviewPanel
                applicationId={data.applicationId}
                isActive={commissionPillIndex === 1 && interviewSubTab === "AI-собеседование"}
                candidateFullName={data.candidateSummary.fullName}
              />
            ) : null}
            {interviewSubTab === "Собеседование с комиссией" ? (
              <CommissionInterviewWithCommissionPanel
                applicationId={data.applicationId}
                isActive={commissionPillIndex === 1 && interviewSubTab === "Собеседование с комиссией"}
                readOnly={readOnly}
                candidateFullName={data.candidateSummary.fullName}
              />
            ) : null}
          </div>
        </>
      ) : null}

      {commissionPillIndex === 2 ? (
        <div key="commission-decision" className={tabTransitionStyles.tabPanelEnter}>
          <div style={{ display: "grid", gap: 12 }}>
            <h2 style={sectionTitle}>Решение комиссии</h2>
          </div>
          <p style={{ margin: 0, fontSize: 14, lineHeight: 1.2, color: "#626262" }}>
            Просмотр и действия по решению комиссии будут здесь.
          </p>
        </div>
      ) : null}
    </div>
  );
}
