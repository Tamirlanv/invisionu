import { FaceDetectionResult } from "../types.js";

export interface FaceDetectionProvider {
  detectFaces(framePaths: string[], sampledTimestampsSec: number[]): Promise<FaceDetectionResult[]>;
}
