import { pgPool } from "../db/pg.js";
import { enqueueCheck } from "../queue/producer.js";
import {
  addAuditEvent,
  createRun,
  getLatestReportByApplication,
  getRunReport,
  updateCheckStatus
} from "../repositories/validationOrchestratorRepository.js";
import { summarizeReport } from "./reportAggregator.js";
import { CheckType, SubmitValidationRunBody } from "./types.js";

export async function submitValidationRun(input: SubmitValidationRunBody): Promise<{ runId: string }> {
  const checkTypes: CheckType[] = [];
  if (input.checks.links) checkTypes.push("links");
  if (input.checks.videoPresentation) checkTypes.push("videoPresentation");
  if (input.checks.certificates) checkTypes.push("certificates");
  const run = await createRun(pgPool, {
    candidateId: input.candidateId,
    applicationId: input.applicationId,
    checks: checkTypes
  });
  if (input.checks.links) {
    try {
      await enqueueCheck("links", {
        runId: run.runId,
        applicationId: input.applicationId,
        url: input.checks.links.url
      });
    } catch (error) {
      await updateCheckStatus(pgPool, {
        runId: run.runId,
        checkType: "links",
        status: "failed",
        lastError: error instanceof Error ? error.message : "queue enqueue failed"
      });
    }
  }
  if (input.checks.videoPresentation) {
    try {
      await enqueueCheck("videoPresentation", {
        runId: run.runId,
        applicationId: input.applicationId,
        videoUrl: input.checks.videoPresentation.videoUrl
      });
    } catch (error) {
      await updateCheckStatus(pgPool, {
        runId: run.runId,
        checkType: "videoPresentation",
        status: "failed",
        lastError: error instanceof Error ? error.message : "queue enqueue failed"
      });
    }
  }
  if (input.checks.certificates) {
    try {
      await enqueueCheck("certificates", {
        runId: run.runId,
        applicationId: input.applicationId,
        imagePath: input.checks.certificates.imagePath
      });
    } catch (error) {
      await updateCheckStatus(pgPool, {
        runId: run.runId,
        checkType: "certificates",
        status: "failed",
        lastError: error instanceof Error ? error.message : "queue enqueue failed"
      });
    }
  }
  await addAuditEvent(pgPool, {
    runId: run.runId,
    checkType: null,
    eventType: "run_created_and_queued",
    payload: { checkTypes }
  });
  return run;
}

export async function getValidationReport(runId: string) {
  const report = await getRunReport(pgPool, runId);
  return report ? summarizeReport(report) : null;
}

export async function getLatestValidationReport(applicationId: string) {
  const report = await getLatestReportByApplication(pgPool, applicationId);
  return report ? summarizeReport(report) : null;
}

export async function reprocessRun(runId: string, checks?: CheckType[]): Promise<void> {
  const report = await getRunReport(pgPool, runId);
  if (!report) return;
  const targets = checks && checks.length ? checks : (["links", "videoPresentation", "certificates"] as CheckType[]);
  for (const c of targets) {
    if (c === "links" && report.checks.links?.result?.url) {
      await enqueueCheck("links", { runId, applicationId: report.applicationId, url: report.checks.links.result.url });
    }
    if (c === "videoPresentation" && report.checks.videoPresentation?.result?.videoUrl) {
      await enqueueCheck("videoPresentation", {
        runId,
        applicationId: report.applicationId,
        videoUrl: report.checks.videoPresentation.result.videoUrl
      });
    }
    if (c === "certificates" && report.checks.certificates?.result?.imagePath) {
      await enqueueCheck("certificates", {
        runId,
        applicationId: report.applicationId,
        imagePath: report.checks.certificates.result.imagePath
      });
    }
  }
  await addAuditEvent(pgPool, {
    runId,
    checkType: null,
    eventType: "run_reprocess_queued",
    payload: { checks: targets }
  });
}
