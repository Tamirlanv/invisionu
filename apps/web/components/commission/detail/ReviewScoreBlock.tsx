"use client";

import { useState, useCallback, useEffect } from "react";
import type { ReviewScoreBlock as ReviewScoreBlockType, ReviewScoreItem } from "@/lib/commission/types";

type Props = {
  data: ReviewScoreBlockType;
  onSave: (scores: Array<{ key: string; score: number }>) => Promise<void>;
  canEdit?: boolean;
};

const MAX_SCORE = 5;

function ScoreCard({
  item,
  isEditing,
  onSelect,
  onStartEdit,
  highlight,
}: {
  item: ReviewScoreItem;
  isEditing: boolean;
  onSelect: (score: number) => void;
  onStartEdit: () => void;
  highlight?: boolean;
}) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        gap: 8,
        padding: 16,
        borderRadius: 16,
        border: highlight ? "2px solid #98da00" : "1px solid #f1f1f1",
        background: "#fff",
        cursor: isEditing ? "default" : "pointer",
      }}
      onClick={() => {
        if (!isEditing) onStartEdit();
      }}
    >
      <p
        style={{
          margin: 0,
          fontSize: 16,
          fontWeight: 450,
          color: "#262626",
          letterSpacing: "-0.48px",
          lineHeight: "16px",
        }}
      >
        {item.label}
      </p>

      {isEditing ? (
        <div style={{ display: "flex", gap: 8 }}>
          {Array.from({ length: MAX_SCORE }, (_, i) => i + 1).map((val) => (
            <button
              key={val}
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(val);
              }}
              style={{
                width: 36,
                height: 36,
                borderRadius: 8,
                border:
                  val === item.effectiveScore
                    ? "2px solid #98da00"
                    : "1px solid #e0e0e0",
                background:
                  val === item.effectiveScore ? "#f4fce3" : "#fff",
                fontSize: 16,
                fontWeight: val === item.effectiveScore ? 550 : 350,
                color: val === item.effectiveScore ? "#4a7c00" : "#262626",
                cursor: "pointer",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                padding: 0,
                transition: "all 0.15s ease",
              }}
            >
              {val}
            </button>
          ))}
        </div>
      ) : (
        <p
          style={{
            margin: 0,
            fontSize: 24,
            fontWeight: 550,
            color: "#98da00",
            letterSpacing: "-0.72px",
            lineHeight: "24px",
          }}
        >
          {item.effectiveScore}/{MAX_SCORE}
        </p>
      )}

      {item.manualScore !== null && !isEditing && (
        <p
          style={{
            margin: 0,
            fontSize: 11,
            fontWeight: 350,
            color: "#9e9e9e",
            letterSpacing: "-0.33px",
          }}
        >
          рек. {item.recommendedScore}
        </p>
      )}
    </div>
  );
}

export function ReviewScoreBlock({ data, onSave, canEdit = true }: Props) {
  const [localItems, setLocalItems] = useState<ReviewScoreItem[]>(data.items);
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    setLocalItems(data.items);
    setEditingKey(null);
    setDirty(false);
  }, [data]);

  const handleSelect = useCallback((key: string, score: number) => {
    setLocalItems((prev) =>
      prev.map((item) =>
        item.key === key
          ? { ...item, manualScore: score, effectiveScore: score }
          : item,
      ),
    );
    setEditingKey(null);
    setDirty(true);
  }, []);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      const scores = localItems
        .filter((item) => item.manualScore !== null)
        .map((item) => ({ key: item.key, score: item.manualScore! }));
      await onSave(scores);
      setDirty(false);
    } finally {
      setSaving(false);
    }
  }, [localItems, onSave]);

  const totalScore = localItems.reduce((sum, item) => sum + item.effectiveScore, 0);

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <div style={{ display: "grid", gap: 4 }}>
        <h3
          style={{
            margin: 0,
            fontSize: 20,
            fontWeight: 450,
            color: "#262626",
            letterSpacing: "-0.6px",
            lineHeight: "20px",
          }}
        >
          Итог
        </h3>
        <p
          style={{
            margin: 0,
            fontSize: 14,
            fontWeight: 350,
            color: "#626262",
            letterSpacing: "-0.42px",
            lineHeight: "14px",
          }}
        >
          Несет рекомендательный характер
        </p>
      </div>

      <div
        style={{
          display: "grid",
          gridTemplateColumns: "1fr 1fr",
          gap: 8,
        }}
      >
        {localItems.map((item) => (
          <ScoreCard
            key={item.key}
            item={item}
            isEditing={canEdit && editingKey === item.key}
            onSelect={(score) => handleSelect(item.key, score)}
            onStartEdit={() => canEdit && setEditingKey(item.key)}
          />
        ))}

        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            padding: 16,
            borderRadius: 16,
            border: "2px solid #98da00",
            background: "#fff",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 16,
              fontWeight: 450,
              color: "#262626",
              letterSpacing: "-0.48px",
              lineHeight: "16px",
            }}
          >
            Итого
          </p>
          <p
            style={{
              margin: 0,
              fontSize: 24,
              fontWeight: 550,
              color: "#98da00",
              letterSpacing: "-0.72px",
              lineHeight: "24px",
            }}
          >
            {totalScore}/{data.maxTotalScore}
          </p>
        </div>
      </div>

      {canEdit && (
        <div style={{ display: "flex", justifyContent: "flex-end" }}>
          <button
            type="button"
            disabled={saving || !dirty}
            onClick={handleSave}
            style={{
              padding: "10px 24px",
              borderRadius: 8,
              border: "none",
              background: dirty ? "#98da00" : "#e0e0e0",
              color: dirty ? "#fff" : "#9e9e9e",
              fontSize: 14,
              fontWeight: 450,
              letterSpacing: "-0.42px",
              cursor: dirty ? "pointer" : "default",
              opacity: saving ? 0.6 : 1,
              transition: "all 0.2s ease",
            }}
          >
            {saving ? "Сохранение..." : "Сохранить"}
          </button>
        </div>
      )}
    </div>
  );
}
