"use client";

import { COMMISSION_STAGE_ORDER, COMMISSION_STAGE_TITLES } from "@/lib/commission/constants";
import type { CommissionStage } from "@/lib/commission/types";

export function StagePipeline({ currentStage }: { currentStage: CommissionStage }) {
  const currentIndex = Math.max(0, COMMISSION_STAGE_ORDER.indexOf(currentStage));
  return (
    <section className="card" style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
      {COMMISSION_STAGE_ORDER.map((stage, idx) => (
        <span
          key={stage}
          style={{
            padding: "6px 10px",
            borderRadius: 999,
            border: "1px solid #e1e1e1",
            background: idx === currentIndex ? "#262626" : idx < currentIndex ? "#f3f3f3" : "#fff",
            color: idx === currentIndex ? "#fff" : "#262626",
          }}
        >
          {COMMISSION_STAGE_TITLES[stage]}
        </span>
      ))}
    </section>
  );
}

