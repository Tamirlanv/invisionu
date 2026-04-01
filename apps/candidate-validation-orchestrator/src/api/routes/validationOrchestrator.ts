import { FastifyInstance } from "fastify";
import { z } from "zod";

import {
  getLatestValidationReport,
  getValidationReport,
  reprocessRun,
  submitValidationRun
} from "../../services/orchestratorService.js";

const SubmitBody = z.object({
  candidateId: z.string().uuid(),
  applicationId: z.string().uuid(),
  checks: z.object({
    links: z.object({ url: z.string().min(1) }).nullable().optional(),
    videoPresentation: z.object({ videoUrl: z.string().min(1) }).nullable().optional(),
    certificates: z.object({ imagePath: z.string().min(1) }).nullable().optional()
  })
});

const ReprocessBody = z.object({
  checks: z.array(z.enum(["links", "videoPresentation", "certificates"])).optional()
});

export async function registerValidationOrchestratorRoutes(app: FastifyInstance): Promise<void> {
  app.post("/candidate-validation/runs", async (req, reply) => {
    const body = SubmitBody.parse(req.body);
    const out = await submitValidationRun(body);
    return reply.send(out);
  });

  app.get("/candidate-validation/runs/:runId", async (req, reply) => {
    const runId = (req.params as { runId: string }).runId;
    const report = await getValidationReport(runId);
    if (!report) return reply.code(404).send({ error: "run_not_found" });
    return reply.send(report);
  });

  app.get("/candidate-validation/applications/:applicationId/latest", async (req, reply) => {
    const applicationId = (req.params as { applicationId: string }).applicationId;
    const report = await getLatestValidationReport(applicationId);
    if (!report) return reply.code(404).send({ error: "not_found" });
    return reply.send(report);
  });

  app.post("/candidate-validation/runs/:runId/reprocess", async (req, reply) => {
    const runId = (req.params as { runId: string }).runId;
    const body = ReprocessBody.parse(req.body ?? {});
    await reprocessRun(runId, body.checks);
    return reply.send({ status: "queued" });
  });
}
