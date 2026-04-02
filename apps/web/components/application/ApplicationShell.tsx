"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, apiFetch, apiFetchCached, bustApiCache } from "@/lib/api-client";
import { getApplicationCompletionSummary, type ReviewSectionState } from "@/lib/application-completion";
import { isDataVerificationStage, type CandidateApplicationStatus } from "@/lib/candidate-status";
import { buildDataVerificationCopy } from "@/lib/data-verification-copy";
import { clearAllDrafts } from "@/lib/draft-storage";
import { ApplicationHeader } from "./ApplicationHeader";
import { ApplicationStickyNav } from "./ApplicationStickyNav";
import { ApplicationSidebar } from "./ApplicationSidebar";
import { DataVerificationView } from "./DataVerificationView";
import { ApplicationFooter } from "./ApplicationFooter";
import { SubmitConfirmationModal, type ModalDocument } from "./SubmitConfirmationModal";
import styles from "./application-shell.module.css";

const ME_TTL_MS = 5 * 60 * 1000;
const STATUS_TTL_MS = 2 * 60 * 1000;

type ReviewData = {
  application_id: string;
  state: string;
  current_stage: string;
  locked: boolean;
  completion_percentage: number;
  missing_sections: string[];
  sections: Record<string, ReviewSectionState>;
  documents: { id: string; document_type: string; original_filename: string; byte_size: number }[];
  required_sections: string[];
};

type SubmitResponse = {
  application_id: string;
  state: string;
  current_stage: string;
  submitted_at: string | null;
  locked_after_submit: boolean;
  submit_outcome?: {
    submitted: boolean;
    stage_transitioned: boolean;
    commission_projection_created: boolean;
    queue_status: "ready" | "degraded" | string;
    queue_failures_count: number;
    queue_message: string | null;
  };
};

type Props = {
  children: React.ReactNode;
};

export function ApplicationShell({ children }: Props) {
  const [firstName, setFirstName] = useState<string | undefined>(undefined);
  const [emailVerified, setEmailVerified] = useState(false);
  const [statusData, setStatusData] = useState<CandidateApplicationStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [review, setReview] = useState<ReviewData | null>(null);
  const [reviewLoading, setReviewLoading] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const data = await apiFetchCached<{
          user: { email_verified: boolean };
          profile?: { first_name?: string } | null;
        }>("/auth/me", ME_TTL_MS);
        if (cancelled) return;
        const part = data.profile?.first_name?.trim();
        if (part) setFirstName(part);
        setEmailVerified(data.user?.email_verified ?? false);
      } catch {
        /* unauthenticated or network */
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const loadReview = useCallback(async () => {
    setReviewLoading(true);
    setReviewError(null);
    try {
      const r = await apiFetch<ReviewData>("/candidates/me/application/review");
      setReview(r);
    } catch (error) {
      setReviewError(error instanceof Error ? error.message : "Не удалось получить статус анкеты");
      setReview(null);
    } finally {
      setReviewLoading(false);
    }
  }, []);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const status = await apiFetchCached<CandidateApplicationStatus>("/candidates/me/application/status", STATUS_TTL_MS);
      setStatusData(status);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        // No application exists (deleted or brand-new candidate) — clear stale cache/drafts
        // and render fresh empty forms, no error shown.
        bustApiCache("/candidates/me/application");
        bustApiCache("/candidates/me/application/status");
        bustApiCache("/candidates/me/application/review");
        clearAllDrafts();
        setStatusData(null);
      } else {
        setStatusData(null);
        setStatusError(error instanceof Error ? error.message : "Не удалось получить этап заявки");
      }
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  function handleOpenModal() {
    setReview(null);
    setModalOpen(true);
    void loadReview();
  }

  async function handleSubmit(): Promise<SubmitResponse> {
    const submitResponse = await apiFetch<SubmitResponse>("/candidates/me/application/submit", { method: "POST" });
    bustApiCache("/candidates/me");
    bustApiCache("/candidates/me/application/review");
    bustApiCache("/candidates/me/application/status");
    bustApiCache("/auth/me");
    clearAllDrafts();
    await loadReview();
    await loadStatus();
    return submitResponse;
  }

  const handleRetrySubmit = useCallback(async () => {
    await apiFetch("/candidates/me/application/retry-submit", { method: "POST" });
    bustApiCache("/candidates/me");
    bustApiCache("/candidates/me/application/review");
    bustApiCache("/candidates/me/application/status");
    await loadReview();
    await loadStatus();
  }, [loadReview, loadStatus]);

  const completionSummary = useMemo(
    () =>
      getApplicationCompletionSummary({
        requiredSections: review?.required_sections ?? [],
        missingSections: review?.missing_sections ?? [],
        sections: review?.sections ?? {},
        locked: review?.locked ?? false,
        emailVerified,
      }),
    [emailVerified, review],
  );

  const modalDocs: ModalDocument[] = (review?.documents ?? []).map((d) => ({
    id: d.id,
    document_type: d.document_type,
    original_filename: d.original_filename,
    byte_size: d.byte_size,
  }));

  const inDataVerificationStage = isDataVerificationStage(statusData);
  const dataVerificationCopy = useMemo(() => buildDataVerificationCopy(statusData), [statusData]);

  return (
    <div className={styles.page}>
      <ApplicationHeader
        candidateName={firstName}
        subtitle={
          inDataVerificationStage
            ? dataVerificationCopy.stageHint
            : "Заполните форму, загрузите документы и отправляйте заявку"
        }
        showSubmitButton={!inDataVerificationStage}
        onSubmitClick={handleOpenModal}
      />
      {!inDataVerificationStage ? <ApplicationStickyNav /> : null}
      <div className={styles.layoutRow}>
        <main className={styles.main}>
          {statusLoading && !statusData ? (
            <p className="muted">Загрузка этапа...</p>
          ) : inDataVerificationStage ? (
            <DataVerificationView status={statusData} onRetrySubmit={handleRetrySubmit} />
          ) : (
            children
          )}
        </main>
        <div className={styles.sidebarCol}>
          <ApplicationSidebar statusData={statusData} statusError={statusError} statusLoading={statusLoading} />
        </div>
      </div>
      <ApplicationFooter />

      <SubmitConfirmationModal
        open={modalOpen}
        onClose={() => setModalOpen(false)}
        onConfirm={handleSubmit}
        completionSummary={completionSummary}
        reviewLoading={reviewLoading}
        reviewError={reviewError}
        onRetryReview={() => void loadReview()}
        documents={modalDocs}
      />
    </div>
  );
}
