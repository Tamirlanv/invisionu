export const GROWTH_QUESTION_IDS = ["q1", "q2", "q3", "q4", "q5"] as const;
export type GrowthQuestionId = (typeof GROWTH_QUESTION_IDS)[number];

export const GROWTH_CHAR_LIMITS: Record<GrowthQuestionId, { min: number; max: number }> = {
  q1: { min: 250, max: 700 },
  q2: { min: 200, max: 700 },
  q3: { min: 200, max: 700 },
  q4: { min: 200, max: 700 },
  q5: { min: 150, max: 700 },
};

export const GROWTH_QUESTIONS: { id: GrowthQuestionId; label: string }[] = [
  {
    id: "q1",
    label:
      "Опишите опыт, проект, инициативу или жизненную ситуацию, которые сильнее всего повлияли на ваш путь.",
  },
  {
    id: "q2",
    label:
      "С какой значимой трудностью, ограничением или препятствием вы столкнулись, и как вы с этим справлялись?",
  },
  {
    id: "q3",
    label:
      "Расскажите о случае, когда вы сами что-то начали, организовали, улучшили или взяли на себя ответственность.",
  },
  {
    id: "q4",
    label:
      "Чему вы научились за последние 1–3 года и что в вашем подходе к учебе, работе или жизни изменилось?",
  },
  {
    id: "q5",
    label:
      "Есть ли у вас достижение, которым вы особенно гордитесь? Расскажите, что стояло за ним и почему оно для вас важно",
  },
];
