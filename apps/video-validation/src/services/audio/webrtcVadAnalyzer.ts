import { readFile } from "node:fs/promises";

import { VadResult } from "../types.js";
import { VadProvider } from "./vadProvider.js";

export class EnergyVadAnalyzer implements VadProvider {
  async analyzeSpeech(wavPath: string): Promise<VadResult> {
    const buffer = await readFile(wavPath);
    if (buffer.length <= 44) {
      return { hasSpeech: false, speechSegmentCount: 0, speechCoverageRatio: 0 };
    }

    const pcm = buffer.subarray(44);
    const sampleCount = Math.floor(pcm.length / 2);
    const frameSize = 1600; // 100ms @16kHz
    const frameCount = Math.floor(sampleCount / frameSize);
    let speechFrames = 0;
    let speechSegments = 0;
    let inSpeech = false;

    for (let frame = 0; frame < frameCount; frame += 1) {
      let energy = 0;
      const frameOffset = frame * frameSize * 2;
      for (let i = 0; i < frameSize; i += 1) {
        const sample = pcm.readInt16LE(frameOffset + i * 2);
        energy += Math.abs(sample);
      }
      const avgEnergy = energy / frameSize;
      const isSpeech = avgEnergy > 700;
      if (isSpeech) {
        speechFrames += 1;
        if (!inSpeech) {
          inSpeech = true;
          speechSegments += 1;
        }
      } else {
        inSpeech = false;
      }
    }

    const ratio = frameCount > 0 ? Number((speechFrames / frameCount).toFixed(3)) : 0;
    return {
      hasSpeech: ratio > 0.05,
      speechSegmentCount: speechSegments,
      speechCoverageRatio: ratio
    };
  }
}
