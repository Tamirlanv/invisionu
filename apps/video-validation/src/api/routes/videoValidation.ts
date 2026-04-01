import { FastifyInstance } from "fastify";
import { z } from "zod";

import { validateVideoPresentation } from "../../services/videoValidationOrchestrator.js";

const BodySchema = z.object({
  videoUrl: z.string().min(1),
  applicationId: z.string().uuid().optional(),
  includeSummary: z.boolean().optional()
});

export async function registerVideoValidationRoutes(app: FastifyInstance): Promise<void> {
  app.post("/video-validation/validate", async (request, reply) => {
    const body = BodySchema.parse(request.body);
    const result = await validateVideoPresentation(body);
    return reply.send(result);
  });
}
