import { describe, expect, it } from "vitest";
import { formatApiErrorBody } from "./api-client";
import { getUserFacingMessage } from "./user-facing-errors";

describe("getUserFacingMessage", () => {
  it("hides 5xx and proxy errors", () => {
    const msg = "Не удалось отправить письмо с кодом: The invision.kz domain is not verified";
    expect(getUserFacingMessage(500, msg)).toMatch(/Сервис временно недоступен/);
    expect(getUserFacingMessage(502, msg)).toMatch(/Сервис временно недоступен/);
    expect(getUserFacingMessage(503, msg)).toMatch(/Сервис временно недоступен/);
  });

  it("strips resend URLs from client-visible path", () => {
    const raw =
      "Не удалось отправить письмо с кодом: Please verify https://resend.com/domains";
    expect(getUserFacingMessage(400, raw)).toMatch(/Запрос не выполнен|Попробуйте позже/);
  });

  it("keeps short safe 400 messages", () => {
    expect(getUserFacingMessage(400, "Некорректная ссылка на документ")).toBe(
      "Некорректная ссылка на документ",
    );
  });

  it("keeps registration conflict for email-already-exists", () => {
    expect(getUserFacingMessage(409, "Этот email уже зарегистрирован.")).toBe("Этот email уже зарегистрирован.");
  });

  it("maps submit-lock conflict to application-specific message", () => {
    expect(getUserFacingMessage(409, "После отправки заявление недоступно для редактирования")).toBe(
      "Анкета уже отправлена и больше не редактируется.",
    );
  });

  it("maps unknown 409 to generic conflict hint", () => {
    expect(getUserFacingMessage(409, "anything from server")).toBe("Конфликт данных. Обновите страницу и повторите.");
  });

  it("shows specific message for retry-submit 409", () => {
    expect(
      getUserFacingMessage(
        409,
        "Повторная отправка доступна только если во втором этапе произошла ошибка запуска обработки.",
      ),
    ).toBe("Переотправка доступна только если второй этап запущен с ошибкой обработки.");
  });

  it("shows clearer message for 403", () => {
    expect(getUserFacingMessage(403, "forbidden")).toBe("Нет доступа. Войдите под аккаунтом кандидата.");
  });

  it("shows email verification hint for submit 403", () => {
    expect(getUserFacingMessage(403, "Подтвердите email перед отправкой заявления")).toBe(
      "Подтвердите email перед отправкой анкеты.",
    );
  });

  it("shows submit-pipeline message for readiness 503", () => {
    expect(getUserFacingMessage(503, "Сервис обработки заявок временно недоступен. Попробуйте отправить анкету позже.")).toBe(
      "Сервис обработки анкеты временно недоступен. Попробуйте отправить позже.",
    );
  });

  it("extracts message from structured FastAPI detail for submit 503", () => {
    const msg = formatApiErrorBody({
      detail: {
        message: "Сервис обработки заявок временно недоступен. Попробуйте отправить анкету позже.",
        code: "submit_pipeline_worker",
      },
    });
    expect(getUserFacingMessage(503, msg)).toBe(
      "Сервис обработки анкеты временно недоступен. Попробуйте отправить позже.",
    );
  });
});
