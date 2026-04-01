import { FastifyInstance } from "fastify";
import { z } from "zod";

import { validateCertificateImage } from "../../services/certificateValidationOrchestrator.js";

const BodySchema = z.object({
  imagePath: z.string().min(1),
  applicationId: z.string().uuid().optional(),
  includeSummary: z.boolean().optional()
});

export async function registerCertificateValidationRoutes(app: FastifyInstance): Promise<void> {
  app.post("/certificate-validation/validate", async (request, reply) => {
    const body = BodySchema.parse(request.body);
    const result = await validateCertificateImage(body);
    return reply.send(result);
  });
}
