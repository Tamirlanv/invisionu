/** Русские подписи к кодам, приходящим из API */

export function applicationStageRu(code: string): string {
  const m: Record<string, string> = {
    application: "Подача заявления",
    initial_screening: "Проверка данных",
    application_review: "Рассмотрение заявления",
    interview: "Собеседование",
    committee_review: "Решение комиссии",
    decision: "Итоговое решение",
  };
  return m[code] ?? code.replaceAll("_", " ");
}

export function applicationStateRu(code: string): string {
  const m: Record<string, string> = {
    draft: "Черновик",
    in_progress: "В процессе заполнения",
    submitted: "Подана",
    under_screening: "Проверка данных",
    under_review: "На рассмотрении",
    interview_pending: "Ожидается собеседование",
    interview_completed: "Собеседование пройдено",
    committee_review: "Рассмотрение комиссией",
    decision_made: "Решение принято",
  };
  return m[code] ?? code;
}

export function missingItemRu(key: string): string {
  const sections: Record<string, string> = {
    "section:personal": "Раздел «Личные данные»",
    "section:contact": "Раздел «Контакты»",
    "section:education": "Раздел «Образование»",
    "section:internal_test": "Тест",
    "section:social_status_cert": "Справка о социальном статусе",
    "document:certificate_of_social_status": "Документ: справка о социальном статусе",
  };
  return sections[key] ?? key;
}

export function sectionKeyRu(key: string): string {
  const m: Record<string, string> = {
    personal: "Личная информация",
    contact: "Контакты",
    education: "Образование",
    internal_test: "Тест",
    motivation_goals: "Мотивация",
    growth_journey: "Путь",
    achievements_activities: "Достижения",
    social_status_cert: "Справка о социальном статусе",
  };
  return m[key] ?? key;
}

export function verificationStatusRu(code: string): string {
  const m: Record<string, string> = {
    pending: "на проверке",
    verified: "проверен",
    rejected: "отклонён",
  };
  return m[code] ?? code;
}

export function documentTypeRu(code: string): string {
  const m: Record<string, string> = {
    certificate_of_social_status: "Справка о социальном статусе",
    transcript: "Транскрипт / ведомость",
    portfolio: "Портфолио",
    essay: "Эссе",
  };
  return m[code] ?? code;
}

export function questionCategoryRu(code: string): string {
  const m: Record<string, string> = {
    logical_reasoning: "Логика",
    situational_judgement: "Ситуационное суждение",
    self_reflection: "Самоанализ",
    leadership_scenarios: "Лидерство",
  };
  return m[code] ?? code;
}

export function questionTypeRu(code: string): string {
  const m: Record<string, string> = {
    text: "текст",
    single_choice: "один вариант",
    multi_choice: "несколько вариантов",
  };
  return m[code] ?? code;
}
