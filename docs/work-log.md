# Журнал реализации

Хронологический лог технических решений: что сделано, зачем, какие файлы затронуты, как проверено. Каждая запись готова к копированию в раздел «Реализация» дипломного отчёта.

---

## M0. Базовый каркас системы (initial commit `4cbec1e`)

**Что сделано.**
Полный end-to-end MVP: контейнерная инфраструктура (Postgres, RabbitMQ, MinIO), Spring Boot backend с JWT-аутентификацией и REST API, FastAPI ML-сервис на EfficientNet-B0 с эвристическим fallback'ом, React-клиент в стилистике brutalist gallery, асинхронный pipeline upload → classify → display через очередь сообщений.

**Архитектурные решения.**
Микросервисное разделение Java backend (бизнес-логика, CRUD, авторизация) и Python ML-сервиса (инференс) — каждая платформа сильна в своей области, смешивание увеличивает связанность. RabbitMQ direct-exchange как точка интеграции: backend публикует задачи, ML потребляет, результат идёт обратно через отдельную очередь — обе стороны знают только про exchange. MinIO как S3-совместимое хранилище: прозрачная миграция в AWS S3 без изменения кода. JWT без серверных сессий — горизонтальное масштабирование backend без shared state.

**Файлы.** `docker-compose.yml`, `backend/**`, `ml-service/**`, `frontend/**`, `README.md`, `.gitignore`.

**Проверка.**
- Регистрация и логин возвращают валидный JWT.
- Загрузка JPEG → запись в БД со статусом `PENDING`, файл в MinIO, сообщение в `classification.tasks`.
- Через ~2 секунды статус переходит в `DONE`, в `photo_styles` появляются 3 строки (top-3 стилей).
- `GET /api/photos/search?style=moody` возвращает только фото с этим тегом.
- Frontend на :5173 отображает галерею в брутальном тёмном стиле, модалка с анализом стилей и similar photos работает.

---

## M1. Удаление фотографий

**Что сделано.**
Эндпоинт `DELETE /api/photos/{id}` с авторизацией по владельцу: удаляет запись из БД (каскадно — связи `photo_styles`) и объект из MinIO. На UI добавлены кнопки удаления: × в углу карточки галереи (видна на hover) и текстовая кнопка `Delete` в модальном окне. Перед удалением — подтверждение через `window.confirm`.

**Архитектурные решения.**
1. **Порядок операций.** Сначала транзакционное удаление из БД (`photoRepository.delete` + cascade на `photo_styles`), затем удаление из MinIO. Если падает MinIO — в БД фотографии уже нет, объект становится «сиротой», но клиент его не увидит. Это допустимо для MVP; в production добавляется фоновый сборщик мусора по списку ключей в БД.
2. **Авторизация.** `findByIdAndUserId` в репозитории — фильтрация по владельцу на уровне SQL-запроса, что исключает horizontal privilege escalation: пользователь не может удалить чужую фотографию даже зная её id. Если фото не принадлежит — 400 Photo not found (не 403, чтобы не раскрывать сам факт существования).
3. **HTTP-семантика.** 204 No Content в ответе — стандарт REST для успешного DELETE без тела.

**Файлы.**
- `backend/src/main/java/com/diploma/psc/photo/MinioService.java` — метод `delete(String key)`.
- `backend/src/main/java/com/diploma/psc/photo/PhotoService.java` — метод `delete(Long id, AuthUser principal)`.
- `backend/src/main/java/com/diploma/psc/photo/PhotoController.java` — `@DeleteMapping("/{id}")`.
- `frontend/src/api.js` — `photoApi.delete`.
- `frontend/src/components/PhotoCell.jsx` — кнопка × с `e.stopPropagation()` чтобы не открыть модалку.
- `frontend/src/components/PhotoModal.jsx` — кнопка Delete в углу изображения.
- `frontend/src/routes/GalleryPage.jsx` — `handleDelete`, оптимистичный апдейт списка.
- `frontend/src/styles.css` — стили `.cell-delete`, `.modal-delete`.

**Проверка.**
```
DELETE /api/photos/6 → 204 No Content
GET    /api/photos/6 → 400 Photo not found
```
Объект пропал из MinIO console, фотография исчезла из галереи без перезагрузки страницы.

---

## M2. Множественная загрузка

**Что сделано.**
Страница `/upload` поддерживает выбор нескольких файлов (drag-and-drop или через диалог), показывает таблицу-очередь с именем файла, размером, прогресс-баром, статусом (Queued / Uploading / Done / Failed). Загрузка идёт параллельно с ограничением concurrency = 3, прогресс по каждому файлу обновляется в реальном времени через `onUploadProgress` axios.

**Архитектурные решения.**
1. **Где параллелить.** Расширять backend ради `POST /api/photos/batch` не нужно: каждая фотография публикует отдельную задачу в RabbitMQ, и pipeline уже умеет обрабатывать их параллельно. Множественность реализуется на клиенте через `Promise.all` с пулом воркеров, что даёт прозрачный прогресс по каждому файлу и не требует изменений API.
2. **Concurrency-лимит.** Три параллельных upload'а — компромисс: больше → перегружаем браузер и сетевой канал, меньше → не используется горизонтальная пропускная способность ML. Реализовано через цикл с общим курсором (`cursor++`), что эквивалентно work-stealing pool без зависимостей.
3. **Идемпотентность retry.** Файлы с `status: 'error'` повторно обрабатываются при следующем нажатии Analyze (фильтр `queued || error` в `onSubmit`). Файлы со статусом `done` пропускаются.
4. **Уникальный id строки.** Используется композит `name+size+lastModified+random` чтобы ключи в React не коллизировали даже при добавлении одного и того же файла дважды.

**Файлы.**
- `frontend/src/routes/UploadPage.jsx` — полная переработка под очередь.
- `frontend/src/api.js` — `photoApi.uploadWithProgress(file, onProgress)`.
- `frontend/src/styles.css` — `.upload-list`, `.upload-row`, прогресс-бары с цветовой индикацией статуса.

**Проверка.**
Загрузка 5 фотографий одной операцией: первые 3 идут параллельно (Uploading), оставшиеся 2 ждут в Queued, как только первый освобождается — следующий стартует. Прогресс-бары двигаются независимо. После завершения всех — автоматический переход в галерею через 600 мс.

---

## M3. Continuous Integration (GitHub Actions)

**Что сделано.**
Добавлен workflow `.github/workflows/ci.yml`, выполняющийся на каждом push и PR в `main`. Четыре независимых job'а:

1. **backend** — JDK 17, `mvn -B verify`, артефакт `*.jar` сохраняется на 7 дней.
2. **frontend** — Node 20, `npm ci`, `npm run build`, артефакт `dist/` сохраняется на 7 дней.
3. **ml-service** — Python 3.11, установка CPU-сборки PyTorch, синтаксическая проверка через `compileall`, smoke-тест: создание `StyleClassifier` и проверка списка стилей.
4. **docker-build** — собирает образы backend и ml-service через Docker Buildx (без push), проверяя что Dockerfile'ы валидные. Запускается после успеха первых трёх.

**Архитектурные решения.**
1. **Отдельные job'ы вместо одного.** Каждый стек (Java / Node / Python) тестируется независимо — это даёт параллельность и понятный фейл-репорт. Если падает только Python — backend и frontend помечены зелёными, проблема локализована.
2. **Кеширование зависимостей.** `cache: maven`, `cache: npm`, `cache: pip` — стандартные actions кешируют зависимости между запусками (~50% экономии времени).
3. **Smoke-тест ML вместо полного прогона.** Pytorch + torchvision из CPU-индекса весит сотни МБ; гонять полные тесты модели в CI смысла нет (нет данных, нет GPU). Достаточно проверить, что зависимости устанавливаются и `StyleClassifier()` инициализируется.
4. **Docker build без push.** В этой работе не настраиваем регистр; задача job'а — поймать опечатку в Dockerfile или ломаную команду. Push в registry добавляется одной строкой `push: true` + login-step, когда понадобится.

**Backend unit-тесты.**
Чистый JUnit 5 + AssertJ, без `@SpringBootTest` (он требует поднятой БД и брокера). 5 тестов на `JwtService`:
- генерация токена помещает email в subject;
- валидный токен проходит `isTokenValid`;
- токен другого пользователя не проходит;
- токен, подписанный другим секретом, отвергается с `SignatureException`;
- истёкший токен (50 ms) отвергается с `ExpiredJwtException`.

Полные интеграционные тесты с реальной БД и брокером — следующий milestone (Testcontainers).

**Файлы.**
- `.github/workflows/ci.yml`
- `backend/src/test/java/com/diploma/psc/auth/JwtServiceTest.java`

**Проверка.**
Локальный прогон через `docker run maven:3.9-eclipse-temurin-17 mvn test`:
```
Tests run: 5, Failures: 0, Errors: 0, Skipped: 0
BUILD SUCCESS
```
После пуша в GitHub workflow появится в Actions tab и будет давать зелёные галочки на коммитах.

---

## M4. Профессиональный README

**Что сделано.**
README переработан в формат, ожидаемый от open-source/корпоративного проекта: shields-бейджи (CI status, Java/Spring/Python/PyTorch/React/Vite/Docker), ASCII-схема архитектуры, таблица технологического стека, плейсхолдеры скриншотов, таблицы с точками входа и REST API, инструкции по запуску, инструкция по подгрузке обученной модели, структура репозитория, dev-команды.

**Архитектурные решения.**
1. **Бейджи как сигнал доверия.** CI-бейдж показывает рецензенту, что код собирается и тесты проходят без ручной проверки. Технологические бейджи позволяют за 2 секунды понять стек.
2. **Ссылки на отчёт прямо из README.** `docs/REPORT.md` и `docs/work-log.md` упомянуты в структуре репозитория — комиссия с GitHub-страницы попадает прямо в материалы.
3. **Папка `docs/screenshots/`** создана с `.gitkeep`. Скриншоты добавляются после финальной полировки UI.

**Файлы.**
- `README.md` — полная переработка.
- `docs/screenshots/.gitkeep` — placeholder.

**Проверка.**
Markdown рендерится в GitHub корректно (бейджи кликабельны, ASCII-схема в `<pre>`-блоке, таблицы выровнены).

---

## M5. Интеграционные тесты с Testcontainers

**Что сделано.**
Добавлен базовый класс `IntegrationTestBase` со статическим singleton-ом из трёх контейнеров (PostgreSQL, RabbitMQ, MinIO), стартующих один раз на весь test-run. Через `@DynamicPropertySource` адреса контейнеров подставляются в Spring-конфигурацию вместо production-настроек. Между тестами `@AfterEach` чистит данные из БД (контейнеры остаются живыми).

**Покрытие.**
1. `AuthFlowTest` (4 теста, реальный HTTP):
   - регистрация → логин → получение JWT;
   - дубликат email → 409;
   - неверный пароль → 401;
   - доступ к защищённому эндпоинту без JWT → 401/403.
2. `ClassificationConsumerTest` (2 теста):
   - публикуется result с `status=OK` → photo переходит в `DONE`, в БД появляются 2 связи photo↔style с правильными FK;
   - публикуется result с `status=ERROR` → photo переходит в `FAILED`, связи отсутствуют.
3. `JwtServiceTest` (5 unit-тестов из M3) — тоже в составе.

Итого **11 тестов, 100% зелёные** на CPU за ~95 секунд (включая старт контейнеров).

**Архитектурные решения.**
1. **Singleton-контейнеры через статический блок.** Ускоряет прогон в 5–10 раз: контейнер Postgres стартует ~3 секунды, MinIO — ~5, RabbitMQ — ~10. Перезапуск на каждый тестовый класс был бы катастрофой.
2. **Очистка данных через репозитории, а не через truncate.** `@AfterEach` вызывает `deleteAll()` в правильном порядке (photoStyles → photos → users) — JPA и cascading FK работают корректно. Альтернатива (Flyway clean / TRUNCATE) разрушает таблицу `styles` со словарными данными, что мешает другим тестам.
3. **Решение проблемы LazyInitializationException.** При `@ManyToOne(fetch=LAZY)` обращение к `ps.getStyle().getName()` вне транзакции бросает исключение — Hibernate-сессия закрыта. Fix: ассерт против `ps.getId().getStyleId()` (FK из embedded id, известен без обращения к прокси), а имена-эталоны достаются упреждающим запросом `styleRepository.findByName()`. Это правильный паттерн для проверки реляций в тестах без `@Transactional` на методе.
4. **TESTCONTAINERS_HOST_OVERRIDE=host.docker.internal** для запуска тестов внутри docker-контейнера maven (DinD-сценарий). Без этого Testcontainers пытается соединиться по `localhost` внутри maven-контейнера, что не работает.

**Файлы.**
- `backend/pom.xml` — добавлены `testcontainers-junit-jupiter`, `testcontainers-postgresql`, `testcontainers-rabbitmq`, `testcontainers-minio`.
- `backend/src/test/java/com/diploma/psc/IntegrationTestBase.java`.
- `backend/src/test/java/com/diploma/psc/auth/AuthFlowTest.java`.
- `backend/src/test/java/com/diploma/psc/classification/ClassificationConsumerTest.java`.

**Проверка.**
```
[INFO] Tests run: 11, Failures: 0, Errors: 0, Skipped: 0
[INFO] BUILD SUCCESS
```

---

## M6. UX: Toast-уведомления и skeleton-плейсхолдеры

**Что сделано.**
1. **Toast-система** через React Context. Провайдер хранит очередь сообщений, рендерит стек в правом нижнем углу, авто-закрытие через 4 секунды (настраивается per-toast), клик закрывает раньше. API: `toast.success(msg)`, `toast.error(msg)`, `toast.info(msg)`. Анимация появления — `cubic-bezier(0.23,1,0.32,1)` 220 ms, в стилистике основного дизайна (border-left цветовой акцент, dot-индикатор).
2. **Skeleton-плейсхолдеры** для галереи. Пока идёт загрузка списка фото — рендерится 18 пустых ячеек той же masonry-сетки (через переиспользование `cellClass(i)`) с shimmer-анимацией (`linear-gradient` + `background-position`). Это гораздо лучше тексткой надписи "Loading", потому что пользователь сразу видит размер и форму будущей галереи.

Toast'ы подключены к login, register, delete. Auth-страницы больше не показывают inline-ошибки — всё через тосты.

**Архитектурные решения.**
1. **Минимальная кастомная имплементация вместо `react-toastify`.** Тосту нужны: очередь, авто-закрытие, anim, 3 типа. Это 50 строк кода — зависимость не оправдана, плюс кастомный стиль гарантирован.
2. **`pointer-events: none` на стеке + `pointer-events: auto` на тосте.** Стек лежит над галереей, но клики проходят сквозь "пустоту" между тостами — пользователь может нажать на фото, не закрыв сначала тост.
3. **Skeleton-сетка использует тот же `cellClass()` паттерн.** При появлении настоящих карточек layout не дрожит — размеры совпадают по index.
4. **Shimmer на CSS, не на canvas/svg.** `linear-gradient` с движущимся `background-position` — GPU-оптимизированный, нагрузки 0.

**Файлы.**
- `frontend/src/ToastContext.jsx` (новый)
- `frontend/src/main.jsx` — обёрнут в `ToastProvider`.
- `frontend/src/routes/LoginPage.jsx`, `RegisterPage.jsx` — inline error → toast.
- `frontend/src/routes/GalleryPage.jsx` — toast на delete success/fail; skeleton-сетка вместо "Loading".
- `frontend/src/components/PhotoCell.jsx` — экспорт `cellClass` (named export) для переиспользования в скелетонах.
- `frontend/src/styles.css` — `.skeleton` + shimmer keyframes; `.toast-stack`, `.toast`, `.toast-{success,error,info}`.

**Проверка.**
`npm run build` → `built in 1.08s`, бандл 218 KB (gzip 73 KB), без warnings. В браузере: введён неверный пароль → красный toast снизу справа, исчезает через 4 секунды или по клику. На главной при первой загрузке — серая мерцающая сетка вместо пустоты.

---

## M7. Страница профиля и эндпоинт статистики

**Что сделано.**
1. **Backend.** Эндпоинт `GET /api/stats/me`, возвращающий агрегацию по фотографиям пользователя:
   - email + дата регистрации;
   - общее количество фото;
   - распределение по статусам (PENDING / DONE / FAILED);
   - топ стилей с count и средней confidence (отсортированы по count убыванию).
2. **Frontend.** Маршрут `/profile`, ссылка в навигации. Три карточки: Account, Library (большое число + status-пиллы), Styles (горизонтальные бары с количеством и средней уверенностью).

**Архитектурные решения.**
1. **Запросы на репозитории `Photo`, не на новой проекции.** Исходно начал делать отдельную псевдо-сущность `StatsRow` — лишний уровень. Правильнее: добавить методы прямо в `PhotoRepository` (`countByUserId`, `countByStatusForUser`, `topStylesByUser`) с интерфейсами-проекциями (`StatusCount`, `StyleStat`). Spring Data JPA маппит native query на интерфейс через свойства-геттеры.
2. **Native query на агрегацию по photo_styles.** JPQL не очень удобен для join + group + aggregate с native СУБД-функцией AVG; SQL короче и читаемее.
3. **EnumMap с предзаполнением нулями.** Если у пользователя нет PENDING-фото, бэкенд всё равно возвращает `"PENDING": 0`. Фронт не должен иметь дело с отсутствующими ключами — это уменьшает количество багов.
4. **Шкала на фронте — относительная.** Бар нормализуется на максимум среди отображённых стилей (`maxCount`), а не на абсолютное число. Это делает визуализацию читаемой при любых масштабах коллекции (от 5 до 5000 фото).

**Файлы.**
- `backend/src/main/java/com/diploma/psc/photo/PhotoRepository.java` — три новых метода + два интерфейса-проекции.
- `backend/src/main/java/com/diploma/psc/stats/StatsResponse.java` — DTO.
- `backend/src/main/java/com/diploma/psc/stats/StatsController.java` — `GET /api/stats/me`.
- `frontend/src/api.js` — `statsApi.me`.
- `frontend/src/routes/ProfilePage.jsx` — новый маршрут.
- `frontend/src/App.jsx` — навигационная ссылка + Route.
- `frontend/src/styles.css` — `.profile-page`, `.profile-card`, `.big-number`, `.status-pill`, `.style-stat-row`.

**Проверка.**
```
GET /api/stats/me →
{
  "email": "demo@test.com",
  "memberSince": "2026-04-20T21:02:27Z",
  "totalPhotos": 2,
  "byStatus": {"PENDING":0, "DONE":2, "FAILED":0},
  "topStyles": [
    {"name":"minimalist","count":2,"avgConfidence":0.236},
    {"name":"airy","count":2,"avgConfidence":0.174},
    {"name":"moody","count":2,"avgConfidence":0.155}
  ]
}
```
В UI: страница показывает 2 фото, всё в DONE, три горизонтальных бара со стилями. `npm run build` зелёный, бандл 220 KB.

---

## M8. UML-диаграммы (Mermaid)

**Тезисы.**
- Диаграммы вынесены в `docs/diagrams.md` — GitHub рендерит Mermaid нативно, без сторонних инструментов.
- Шесть диаграмм: component, sequence (upload+classify end-to-end), class (модель домена), state (жизненный цикл фото), use case, deployment.
- В `docs/REPORT.md` добавлена ссылка на `diagrams.md` из главы 2 — комиссия видит и текст, и визуализации.
- При экспорте в PDF через pandoc Mermaid превращается в код-блоки; для финального PDF — рендерить через `mmdc` (mermaid-cli) в SVG/PNG и подставить.

**Файлы.** `docs/diagrams.md` (новый), `docs/REPORT.md` (одна строка-ссылка).

---

## M9. Раздел про безопасность (OWASP)

**Тезисы для отчёта.**
- Аутентификация: BCrypt (strength 10), JWT HS512, TTL 24h, без серверных сессий.
- Авторизация: фильтрация по `user_id` на уровне SQL (`findByIdAndUserId`) — закрывает IDOR / horizontal privilege escalation. 400 «not found» вместо 403 — не раскрывает существование чужих ID.
- Транспорт: CORS со списком localhost-origin'ов; в production добавить TLS-termination через reverse-proxy.
- Валидация ввода: `@Valid` + Bean Validation (email-формат, min length пароля); MIME-whitelist на upload (`image/jpeg|png|webp`); лимит 25 MB через `spring.servlet.multipart`.
- SQL injection: исключён по конструкции — все запросы через JPA/JPQL/named parameters.
- XSS: React эскейпит по умолчанию; нет `dangerouslySetInnerHTML`; presigned URL'ы не содержат HTML.
- CSRF: отключён сознательно — JWT-only API, нет cookie-based session, нет state-changing форм по `application/x-www-form-urlencoded` от браузера.
- Storage: бакет MinIO с policy `download` для анонимного GET (presigned URL'ы и так временные); ключи объектов префиксированы `user-{id}/uuid` — нет угадываемости.
- Secrets: `JWT_SECRET` через env var, не в коде; `change-me-in-prod` в `application.yml` — заведомо невалидный для production.
- Что **НЕ** закрыто (честно указать в отчёте как future work):
  - rate limiting / brute-force protection на `/auth/login` — нужен Bucket4j или nginx limit_req;
  - audit log;
  - refresh tokens / revocation list;
  - file scanning (антивирусом / на корректность image header'ов помимо MIME);
  - Content Security Policy headers.

**Куда вставить.** В `REPORT.md` — отдельная подглава 6.3 «Информационная безопасность» внутри главы 6 (Развёртывание) или новая глава 7. Тезисы выше можно расписать в 1.5–2 страницы.

---

## Сводная карта сделанного (для разворачивания в отчёт)

| Milestone | Что | Коммит |
|---|---|---|
| M0 | Базовый каркас (backend, ML, frontend, infra) | `4cbec1e` |
| M1 | Удаление фото (DELETE endpoint, UI) | в `9011de3` |
| M2 | Множественная загрузка с per-file прогрессом | в `9011de3` |
| M3 | GitHub Actions CI + JwtService unit-тесты | `1e1fc23` |
| M4 | Профессиональный README с бейджами | в `f3f92ff` |
| M5 | Testcontainers integration tests (11/11) | `35495d6` |
| M6 | Toast-уведомления + skeleton-плейсхолдеры | следующий коммит |
| M7 | Profile page + `/api/stats/me` | следующий коммит |
| M8 | UML-диаграммы Mermaid в `docs/diagrams.md` | следующий коммит |
| M9 | OWASP-разбор (тезисы в этом файле) | будущая работа |

