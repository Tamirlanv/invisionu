import { Pool } from "pg";
import { randomUUID } from "node:crypto";

import { CheckStatus, CheckType, CandidateValidationReport, OverallStatus, ValidationCheckSummary } from "../services/types.js";

export async function createRun(
  pool: Pool,
  input: { candidateId: string; applicationId: string; checks: CheckType[] }
): Promise<{ runId: string }> {
  const runId = randomUUID();
  const run = await pool.query(
    `INSERT INTO candidate_validation_runs (id, candidate_id, application_id, overall_status, warnings, errors, explainability)
     VALUES ($1,$2,$3,'processing','[]'::jsonb,'[]'::jsonb,'[]'::jsonb) RETURNING id`,
    [runId, input.candidateId, input.applicationId]
  );
  for (const check of input.checks) {
    const checkId = randomUUID();
    await pool.query(
      `INSERT INTO candidate_validation_checks (id, run_id, check_type, status, result_payload, attempts)
       VALUES ($1,$2,$3,'pending',NULL,0)`,
      [checkId, runId, check]
    );
  }
  const _ = run;
  return { runId };
}

export async function updateCheckStatus(
  pool: Pool,
  input: {
    runId: string;
    checkType: CheckType;
    status: CheckStatus;
    resultPayload?: Record<string, unknown> | null;
    lastError?: string | null;
    incrementAttempts?: boolean;
  }
): Promise<void> {
  await pool.query(
    `UPDATE candidate_validation_checks
     SET status=$3::text,
         result_payload=COALESCE($4::jsonb,result_payload),
         last_error=COALESCE($5,last_error),
         attempts=attempts + CASE WHEN $6 THEN 1 ELSE 0 END,
         started_at=CASE WHEN $3::text='processing' THEN now() ELSE started_at END,
         finished_at=CASE WHEN $3::text IN ('passed','failed','manual_review_required','skipped') THEN now() ELSE finished_at END,
         updated_at=now()
     WHERE run_id=$1 AND check_type=$2`,
    [input.runId, input.checkType, input.status, input.resultPayload ? JSON.stringify(input.resultPayload) : null, input.lastError ?? null, Boolean(input.incrementAttempts)]
  );
}

export async function addAuditEvent(
  pool: Pool,
  input: { runId: string; checkType: CheckType | null; eventType: string; payload: Record<string, unknown> }
): Promise<void> {
  const checkIdRow = input.checkType
    ? await pool.query(`SELECT id FROM candidate_validation_checks WHERE run_id=$1 AND check_type=$2 LIMIT 1`, [input.runId, input.checkType])
    : null;
  const checkId = checkIdRow?.rows?.[0]?.id ?? null;
  const auditId = randomUUID();
  await pool.query(
    `INSERT INTO candidate_validation_audit_events (id, run_id, check_id, event_type, payload) VALUES ($1,$2,$3,$4,$5::jsonb)`,
    [auditId, input.runId, checkId, input.eventType, JSON.stringify(input.payload)]
  );
}

export async function recomputeOverallStatus(pool: Pool, runId: string): Promise<OverallStatus> {
  const rows = await pool.query(`SELECT status FROM candidate_validation_checks WHERE run_id=$1`, [runId]);
  const statuses = rows.rows.map((r) => r.status as CheckStatus);
  let overall: OverallStatus = "processing";
  if (statuses.includes("processing")) overall = "processing";
  else if (statuses.includes("manual_review_required")) overall = "manual_review_required";
  else if (statuses.includes("failed")) overall = "failed";
  else if (statuses.some((s) => s === "pending" || s === "skipped")) overall = "partially_processed";
  else overall = "passed";
  await pool.query(`UPDATE candidate_validation_runs SET overall_status=$2, updated_at=now() WHERE id=$1`, [runId, overall]);
  return overall;
}

export async function getRunReport(pool: Pool, runId: string): Promise<CandidateValidationReport | null> {
  const run = await pool.query(`SELECT * FROM candidate_validation_runs WHERE id=$1`, [runId]);
  if (!run.rows.length) return null;
  const checks = await pool.query(`SELECT * FROM candidate_validation_checks WHERE run_id=$1`, [runId]);
  const map: Record<string, ValidationCheckSummary | null> = {
    links: null,
    videoPresentation: null,
    certificates: null
  };
  for (const row of checks.rows) {
    map[row.check_type] = {
      status: row.status,
      result: row.result_payload,
      updatedAt: row.updated_at.toISOString()
    };
  }
  const r = run.rows[0];
  return {
    candidateId: r.candidate_id,
    applicationId: r.application_id,
    overallStatus: r.overall_status,
    checks: {
      links: map.links,
      videoPresentation: map.videoPresentation,
      certificates: map.certificates
    },
    warnings: r.warnings ?? [],
    errors: r.errors ?? [],
    explainability: r.explainability ?? [],
    updatedAt: r.updated_at.toISOString()
  };
}

export async function getLatestReportByApplication(pool: Pool, applicationId: string): Promise<CandidateValidationReport | null> {
  const row = await pool.query(
    `SELECT id FROM candidate_validation_runs WHERE application_id=$1 ORDER BY updated_at DESC LIMIT 1`,
    [applicationId]
  );
  if (!row.rows.length) return null;
  return getRunReport(pool, String(row.rows[0].id));
}
