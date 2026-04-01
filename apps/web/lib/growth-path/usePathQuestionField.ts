"use client";

import { useCallback, useRef, useState } from "react";
import type { GrowthQuestionId } from "./constants";
import { DEFAULT_GROWTH_ANSWER_META, type GrowthAnswerMetaState } from "./types";

function parseMeta(raw: unknown): GrowthAnswerMetaState {
  if (!raw || typeof raw !== "object") return { ...DEFAULT_GROWTH_ANSWER_META };
  const o = raw as Record<string, unknown>;
  return {
    was_pasted: Boolean(o.was_pasted),
    paste_count: typeof o.paste_count === "number" && o.paste_count >= 0 ? Math.floor(o.paste_count) : 0,
    last_pasted_at: o.last_pasted_at != null ? String(o.last_pasted_at) : null,
    typing_count: typeof o.typing_count === "number" && o.typing_count >= 0 ? Math.floor(o.typing_count) : 0,
    typing_duration_ms:
      typeof o.typing_duration_ms === "number" && o.typing_duration_ms >= 0
        ? Math.floor(o.typing_duration_ms)
        : 0,
    was_edited_after_paste: Boolean(o.was_edited_after_paste),
    delete_count: typeof o.delete_count === "number" && o.delete_count >= 0 ? Math.floor(o.delete_count) : 0,
    revision_count: typeof o.revision_count === "number" && o.revision_count >= 0 ? Math.floor(o.revision_count) : 0,
  };
}

/**
 * Per-question textarea: paste tracking + coarse typing/delete/revision metrics (silent).
 */
export function usePathQuestionField(
  questionId: GrowthQuestionId,
  initialMeta?: Partial<GrowthAnswerMetaState>,
) {
  const [meta, setMeta] = useState<GrowthAnswerMetaState>(() => ({
    ...DEFAULT_GROWTH_ANSWER_META,
    ...initialMeta,
  }));

  const focusAt = useRef<number | null>(null);
  const lastBlurValue = useRef<string>("");
  const pastedSnapshot = useRef<string | null>(null);

  const onFocus = useCallback(() => {
    focusAt.current = Date.now();
  }, []);

  const onPaste = useCallback(() => {
    setMeta((m) => ({
      ...m,
      was_pasted: true,
      paste_count: m.paste_count + 1,
      last_pasted_at: new Date().toISOString(),
    }));
    pastedSnapshot.current = "";
  }, []);

  const onBeforeInput = useCallback((e: React.FormEvent<HTMLTextAreaElement> & { nativeEvent: InputEvent }) => {
    const ne = e.nativeEvent as InputEvent;
    if (ne.inputType?.startsWith("delete")) {
      setMeta((m) => ({ ...m, delete_count: m.delete_count + 1 }));
    }
  }, []);

  const onChangeValue = useCallback((nextRaw: string, prevRaw: string) => {
    setMeta((m) => {
      let wasEdited = m.was_edited_after_paste;
      if (m.was_pasted && m.paste_count > 0 && nextRaw !== prevRaw) {
        wasEdited = true;
      }
      return {
        ...m,
        typing_count: m.typing_count + 1,
        was_edited_after_paste: wasEdited,
      };
    });
  }, []);

  const onBlurValue = useCallback((current: string) => {
    setMeta((m) => {
      let duration = m.typing_duration_ms;
      if (focusAt.current != null) {
        duration += Date.now() - focusAt.current;
        focusAt.current = null;
      }
      let rev = m.revision_count;
      if (current !== lastBlurValue.current && lastBlurValue.current !== "") {
        rev += 1;
      }
      lastBlurValue.current = current;
      return { ...m, typing_duration_ms: duration, revision_count: rev };
    });
  }, []);

  const hydrateFromApi = useCallback((raw: unknown) => {
    setMeta(parseMeta(raw));
  }, []);

  return {
    questionId,
    meta,
    setMeta,
    onFocus,
    onPaste,
    onBeforeInput,
    onChangeValue,
    onBlurValue,
    hydrateFromApi,
  };
}

export type PathQuestionFieldApi = ReturnType<typeof usePathQuestionField>;
