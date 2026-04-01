import { runProcess } from "../../utils/process.js";
import { FaceDetectionResult } from "../types.js";
import { FaceDetectionProvider } from "./faceDetectionProvider.js";

export class OpenCvFaceDetector implements FaceDetectionProvider {
  async detectFaces(framePaths: string[], sampledTimestampsSec: number[]): Promise<FaceDetectionResult[]> {
    const results: FaceDetectionResult[] = [];

    for (let i = 0; i < framePaths.length; i += 1) {
      const framePath = framePaths[i];
      const timestampSec = sampledTimestampsSec[i] ?? i;
      try {
        // Uses OpenCV Haar cascades via python if available.
        const { stdout } = await runProcess("python3", [
          "-c",
          [
            "import cv2,sys",
            "img=cv2.imread(sys.argv[1])",
            "gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)",
            "c=cv2.CascadeClassifier(cv2.data.haarcascades+'haarcascade_frontalface_default.xml')",
            "faces=c.detectMultiScale(gray,1.1,4)",
            "count=len(faces)",
            "conf=0.85 if count>0 else 0.0",
            "print(f'{count},{conf}')"
          ].join(";"),
          framePath
        ]);
        const [countRaw, confRaw] = stdout.trim().split(",");
        const count = Number(countRaw);
        const confidence = Number(confRaw);
        results.push({
          timestampSec,
          detected: Number.isFinite(count) && count > 0,
          confidence: Number.isFinite(confidence) ? confidence : 0
        });
      } catch {
        // Conservative fallback if OpenCV runtime is unavailable.
        results.push({ timestampSec, detected: false, confidence: 0 });
      }
    }

    return results;
  }
}
