# Тестовые документы для проверки парсинга баллов (ЕНТ / IELTS)

Положите сюда **два** файла и при необходимости отредактируйте [`expected.json`](./expected.json).

## Имена в репозитории

| Файл        | Назначение |
|------------|------------|
| `ент.pdf`  | сертификат ЕНТ (кириллическое имя файла) |
| `ielts.jpeg` | сертификат IELTS (скан, OCR через Tesseract) |

Поддерживаются **PDF** (текстовый слой — как в API через `plainText`; скан без текста — первая страница рендерится в растр и идёт в OCR) и **PNG/JPEG** (полный путь OCR). В интеграционном тесте предобработка изображения замокана (без **ffmpeg**); нужен системный **Tesseract** (см. [OCR setup](../../../certificate-validation/docs/ocr-setup.md)). Поле **`ocrLang`** в манифесте задаёт `-l` для Tesseract (например `rus+kaz+eng` для ЕНТ, `eng` для IELTS).

По умолчанию `npm run test:legal` **падает**, если требуется OCR, а Tesseract недоступен. Чтобы пропустить такие кейсы (CI без пакетов): `LEGAL_SKIP_OCR_FIXTURES=1`. Только изображения: `LEGAL_SKIP_IMAGE_FIXTURES=1`.

Строгая проверка балла: `LEGAL_REQUIRE_SCORE` не равен `0` (по умолчанию). Если на скане Tesseract не выделяет цифры в таблице, тест упадёт на сравнении с `expectedScore`. Для прогона «тип документа + реальный вывод OCR без обязательного балла»: `LEGAL_REQUIRE_SCORE=0` (так же задано в Docker-образе для `Dockerfile.legal`).

Воспроизводимый прогон с OCR: `docker build -f apps/certificate-validation/Dockerfile.legal …` и `docker run --rm cert-legal` (см. [OCR setup](../../../certificate-validation/docs/ocr-setup.md)).

## Манифест `expected.json`

Для каждой записи укажите:

- `file` — имя файла в этой папке
- `expectedDocumentType` — `ent` или `ielts`
- `expectedScore` — ожидаемый балл для сравнения с **реально извлечённым** значением из OCR/парсера
- `ocrLang` — (опционально) язык Tesseract `-l`, например `rus+kaz+eng` или `eng`

Персональные данные в репозиторий не коммитьте: при необходимости задайте каталог через `LEGAL_FIXTURES_DIR` и храните файлы локально.

## Запуск

Из каталога `apps/certificate-validation`:

```bash
npm run test:legal
```

Без файлов тесты помечаются как **skipped**.
