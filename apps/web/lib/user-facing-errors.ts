/**
 * Преобразует ответ API в короткое сообщение для UI.
 * Не показываем стеки, URL провайдеров (Resend и т.д.), технические детали инфраструктуры.
 */
const TECH_LEAK = /https?:\/\/|resend\.com|domain is not verified|traceback|exception|internal server|bad gateway/i;

function isLikelySafeUserMessage(t: string): boolean {
  const s = t.trim();
  if (!s || s.length > 600) return false;
  if (TECH_LEAK.test(s)) return false;
  return true;
}

export function getUserFacingMessage(status: number, rawDetail: string): string {
  const t = (rawDetail || "").trim();
  const lowered = t.toLowerCase();

  if (status === 503 && lowered.includes("обработки заявок")) {
    return "Сервис обработки анкеты временно недоступен. Попробуйте отправить позже.";
  }

  if (status >= 500 || status === 502 || status === 503 || status === 504) {
    return "Сервис временно недоступен. Попробуйте позже.";
  }

  if (status === 401) {
    return "Неверный email или пароль.";
  }
  if (status === 403) {
    if (lowered.includes("подтвердите email")) {
      return "Подтвердите email перед отправкой анкеты.";
    }
    return "Нет доступа. Войдите под аккаунтом кандидата.";
  }
  if (status === 404) {
    return "Данные не найдены.";
  }
  if (status === 409) {
    if (lowered.includes("повторная отправка доступна")) {
      return "Переотправка доступна только если второй этап запущен с ошибкой обработки.";
    }
    if (lowered.includes("зарегистрирован") && lowered.includes("email")) {
      return "Этот email уже зарегистрирован.";
    }
    if (lowered.includes("после отправки") || lowered.includes("недоступно для редактирования")) {
      return "Анкета уже отправлена и больше не редактируется.";
    }
    if (lowered.includes("already submitted") || lowered.includes("duplicate")) {
      return "Анкета уже была отправлена ранее.";
    }
    return "Конфликт данных. Обновите страницу и повторите.";
  }

  if (isLikelySafeUserMessage(t)) {
    return t;
  }

  if (status === 422) {
    return "Проверьте введённые данные.";
  }
  if (status === 400) {
    return "Запрос не выполнен. Проверьте данные.";
  }

  return "Не удалось выполнить действие. Попробуйте позже.";
}
