import { FileValidationResult } from "../types.js";

const ALLOWED_MIME = new Set(["image/jpeg", "image/png", "image/webp"]);

export function validateInputFile(file: { mimetype: string; size: number }): FileValidationResult {
  const warnings: string[] = [];
  const errors: string[] = [];
  if (!ALLOWED_MIME.has(file.mimetype)) errors.push("Unsupported file type");
  if (file.size <= 0) errors.push("File is empty");
  if (file.size > 8 * 1024 * 1024) warnings.push("Large image may reduce OCR quality");
  return { isValid: errors.length === 0, warnings, errors };
}
